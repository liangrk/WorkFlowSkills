import subprocess
import time
import os
import sys

lock_script = '.claude/skills/android-shared/bin/android-file-lock'
lock_file = 'test.lock'

# Ensure the lock file doesn't exist
if os.path.exists(lock_file + '.lock.d'):
    import shutil
    shutil.rmtree(lock_file + '.lock.d')

print("Starting first process...")
p1 = subprocess.Popen(['bash', lock_script, lock_file, 'sleep', '2'])

time.sleep(0.5)
print("Starting second process (should wait)...")
start_time = time.time()
p2 = subprocess.Popen(['bash', lock_script, lock_file, 'echo', 'P2 acquired'])

p1.wait()
p2.wait()
end_time = time.time()

duration = end_time - start_time
print(f"Total time: {duration:.2f}s")

if duration >= 2.0:
    print("SUCCESS: P2 waited for P1")
else:
    print("FAILURE: P2 did not wait long enough")
