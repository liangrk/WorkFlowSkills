#!/usr/bin/env python3
"""Android UI Dump - Automated UI hierarchy dumper with visualization."""

import subprocess
import sys
import os
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path


class AndroidUIDumper:
    def __init__(self, package_name=None, output_dir=None):
        self.package_name = package_name
        self.output_dir = output_dir or Path(f"./android-dumps/{datetime.now().strftime('%Y%m%d-%H%M%S')}")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.dump_method = "unknown"

    def run_cmd(self, cmd, timeout=30):
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
            return r.stdout.strip(), r.stderr.strip(), r.returncode
        except Exception as e:
            return "", str(e), -1

    def check_env(self):
        _, _, c = self.run_cmd("adb version")
        if c != 0:
            print("❌ ADB not found. Install: https://developer.android.com/studio/releases/platform-tools")
            return False
        out, _, _ = self.run_cmd("adb devices")
        devices = [l for l in out.split('\n')[1:] if 'device' in l and not l.startswith('*')]
        if not devices:
            print("❌ No device connected")
            return False
        print(f"✅ ADB OK | Device: {devices[0].split()[0]}")
        return True

    def detect_app(self):
        out, _, _ = self.run_cmd("adb shell dumpsys window windows | grep -E 'mCurrentFocus|mFocusedApp'")
        if out:
            m = re.search(r'(com\.[\w.]+)/', out)
            if m:
                print(f"✅ Detected: {m.group(1)}")
                return m.group(1)
        out, _, _ = self.run_cmd("adb shell dumpsys activity recents | grep 'Recent #0'")
        if out:
            m = re.search(r'cmp=(com\.[\w.]+)/', out)
            if m:
                print(f"✅ Detected (fallback): {m.group(1)}")
                return m.group(1)
        print("⚠️ Could not detect app")
        return None

    def dump_uiautomator(self):
        out, err, c = self.run_cmd("adb shell uiautomator dump /sdcard/ui.xml")
        if c != 0:
            print(f"❌ uiautomator failed: {err}")
            return False
        f = self.output_dir / "ui_hierarchy.xml"
        out, err, c = self.run_cmd(f'adb pull /sdcard/ui.xml "{f}"')
        self.run_cmd("adb shell rm /sdcard/ui.xml")
        if c == 0 and f.exists():
            self.dump_method = "uiautomator"
            self._filter_xml(f)
            print(f"✅ UI dump saved: {f}")
            return True
        print(f"❌ Pull failed: {err}")
        return False

    def _filter_xml(self, xml_file):
        """过滤 XML, 只保留目标 App 相关节点 (基于 package 属性)"""
        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()
            pkg = self.package_name or ''
            def filter_node(node):
                # 基于 package 属性判断, 而非 resource-id
                node_pkg = node.get('package', '')
                if node_pkg and pkg and node_pkg != pkg:
                    return False
                to_remove = [ch for ch in node if not filter_node(ch)]
                for ch in to_remove:
                    node.remove(ch)
                return True
            filter_node(root)
            tree.write(xml_file, encoding='unicode', xml_declaration=True)
        except Exception as e:
            print(f"⚠️ XML filter failed: {e}")

    def dump_activity(self):
        if not self.package_name:
            return False
        f = self.output_dir / "activity_dump.txt"
        out, err, c = self.run_cmd(f"adb shell dumpsys activity top {self.package_name}")
        if out:
            f.write_text(out, encoding='utf-8')
            self.dump_method = "dumpsys_activity"
            print(f"✅ Activity dump saved: {f}")
            return True
        print(f"❌ dumpsys failed: {err}")
        return False

    def screenshot(self):
        f = self.output_dir / "screenshot.png"
        self.run_cmd("adb shell screencap -p /sdcard/screen.png")
        out, err, c = self.run_cmd(f'adb pull /sdcard/screen.png "{f}"')
        self.run_cmd("adb shell rm /sdcard/screen.png")
        if c == 0 and f.exists():
            print(f"✅ Screenshot: {f}")
            return True
        return False

    def analyze(self):
        xml = self.output_dir / "ui_hierarchy.xml"
        if not xml.exists():
            return None
        try:
            root = ET.parse(xml).getroot()
            pkg = self.package_name or ''
            stats = {'total_views': 0, 'clickable': 0, 'with_text': 0, 'with_id': 0,
                     'resource_ids': [], 'text_elements': [], 'view_types': {}}
            def walk(node):
                stats['total_views'] += 1
                if node.get('clickable') == 'true': stats['clickable'] += 1
                t = node.get('text', '')
                if t:
                    stats['with_text'] += 1
                    stats['text_elements'].append(t)
                rid = node.get('resource-id', '')
                if rid:
                    stats['with_id'] += 1
                    # 简化 ID (去掉包名前缀)
                    short_id = rid.split('/')[-1] if '/' in rid else rid
                    stats['resource_ids'].append(short_id)
                cls = node.get('class', 'unknown').split('.')[-1]
                stats['view_types'][cls] = stats['view_types'].get(cls, 0) + 1
                for child in node: walk(child)
            walk(root)
            data = {'dump_time': datetime.now().isoformat(), 'package': self.package_name,
                    'dump_method': self.dump_method, **stats}
            af = self.output_dir / "analysis.json"
            json.dump(data, open(af, 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
            print(f"✅ Analysis: {stats['total_views']} views, {stats['clickable']} clickable, {stats['with_id']} IDs")
            return stats
        except Exception as e:
            print(f"❌ Analyze failed: {e}")
            return None

    def report(self, stats=None):
        f = self.output_dir / "report.txt"
        txt = f"UI DUMP | {self.package_name} | {self.dump_method}\n{'='*40}\n"
        if stats:
            txt += f"Views: {stats['total_views']} | Clickable: {stats['clickable']} | IDs: {stats['with_id']}\n"
            if stats['resource_ids']:
                txt += "\nIDs:\n" + '\n'.join(f"  {x}" for x in stats['resource_ids'][:15])
            if stats['text_elements']:
                txt += f"\n\nText ({len(stats['text_elements'])} items):\n" + '\n'.join(f"  {x}" for x in stats['text_elements'][:20])
        f.write_text(txt, encoding='utf-8')

    def html_tree(self):
        xml = self.output_dir / "ui_hierarchy.xml"
        out = self.output_dir / "tree_view.html"
        if not xml.exists(): return
        script = Path(__file__).parent / "parse_ui_xml.py"
        if script.exists():
            _, err, c = self.run_cmd(f'python "{script}" "{str(xml)}" "{str(out)}"')
            if c == 0:
                print(f"✅ HTML: {out}")
                return
            print(f"⚠️ HTML failed: {err}")

    def open_browser(self):
        f = self.output_dir / "tree_view.html"
        if f.exists():
            if sys.platform == 'win32': os.startfile(f)
            elif sys.platform == 'darwin': self.run_cmd(f"open \"{f}\"")
            else: self.run_cmd(f"xdg-open \"{f}\"")

    def dump(self):
        if not self.check_env(): return False
        self.package_name = self.package_name or self.detect_app()
        if not self.package_name:
            print("Usage: python dump_android_ui.py --package com.example.app")
            return False
        ok = self.dump_uiautomator() or self.dump_activity()
        if not ok:
            print("❌ All dump methods failed")
            return False
        self.screenshot()
        stats = self.analyze()
        self.report(stats)
        self.html_tree()
        # 精简输出
        files = list(self.output_dir.iterdir())
        print(f"✅ {self.package_name} | {self.dump_method} | {stats['total_views'] if stats else 0} views")
        print(f"📁 {self.output_dir}")
        print(f"📄 {[f.name for f in files]}")
        return True


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--package', '-p')
    p.add_argument('--output', '-o')
    args = p.parse_args()
    d = AndroidUIDumper(args.package, Path(args.output) if args.output else None)
    sys.exit(0 if d.dump() else 1)

if __name__ == '__main__':
    main()
