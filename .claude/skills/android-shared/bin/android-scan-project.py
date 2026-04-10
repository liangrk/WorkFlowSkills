#!/usr/bin/env python3
"""Helper: reads env vars set by android-scan-project bash script, outputs JSON profile."""
import json, os, sys

def s(key, default=None):
    v = os.environ.get(key, '')
    return v if v and v not in ('', '[]', '0', 'none') else default

def b(key, default=False):
    return os.environ.get(key, '').lower() in ('true', '1', 'yes') if os.environ.get(key) else default

def j(key, default=None):
    v = os.environ.get(key, '')
    try:
        return json.loads(v) if v else default
    except json.JSONDecodeError:
        return default

def n(key, default=None):
    v = os.environ.get(key, '').strip()
    if not v or v == 'none':
        return default
    try:
        return int(v)
    except ValueError:
        return default

data = {
    'meta': {
        'project_name': s('PROJECT_NAME'),
        'package': s('ROOT_PACKAGE'),
        'slug': s('PROJECT_SLUG'),
        'modules': j('MODULES_JSON', []),
        'build_system': s('BUILD_SYSTEM', 'unknown'),
        'kotlin_version': s('KOTLIN_VERSION'),
        'agp_version': s('AGP_VERSION'),
        'compile_sdk': n('COMPILE_SDK'),
        'min_sdk': n('MIN_SDK'),
        'target_sdk': n('TARGET_SDK'),
        'generated_at': s('TIMESTAMP'),
        'scan_version': 1
    },
    'dependencies': {
        'ui': {
            'compose_enabled': b('COMPOSE_ENABLED'),
            'compose_bom': s('COMPOSE_BOM'),
            'compose_compiler': s('COMPOSE_COMPILER'),
            'material3': b('MATERIAL3'),
            'material_components': b('MATERIAL_COMPONENTS'),
            'custom_theme': b('CUSTOM_THEME'),
            'navigation': s('NAVIGATION_TYPE'),
            'image_loading': s('IMAGE_LOADING'),
            'animation': s('ANIMATION_LIB')
        },
        'network': {
            'http_client': s('HTTP_CLIENT'),
            'api_client': s('API_CLIENT'),
            'serializer': s('SERIALIZER'),
            'graphql': s('GRAPHQL'),
            'websocket': s('WEBSOCKET')
        },
        'di': {
            'framework': s('DI_FRAMEWORK'),
            'version': s('DI_VERSION')
        },
        'async': {
            'coroutines': b('COROUTINES'),
            'rxjava': b('RXJAVA'),
            'flow_extensions': b('FLOW_EXTENSIONS')
        },
        'database': {
            'orm': s('ORM'),
            'version': s('ORM_VERSION'),
            'encryption': s('ENCRYPTION'),
            'migration_count': n('MIGRATION_COUNT', 0)
        },
        'storage': {
            'datastore': b('DATASTORE'),
            'shared_preferences': b('SHARED_PREFERENCES'),
            'encrypted_preferences': b('ENCRYPTED_PREFERENCES')
        },
        'image': {
            'loading_library': s('IMAGE_LOADING'),
            'camera': s('CAMERA_X'),
            'image_compression': s('IMAGE_COMPRESSION')
        },
        'media': {
            'exoplayer': b('EXOPLAYER'),
            'camera_x': s('CAMERA_X'),
            'media3': s('MEDIA3')
        },
        'security': {
            'biometric': s('BIOMETRIC'),
            'encryption': s('SECURITY_ENCRYPTION'),
            'certificate_pinning': b('CERTIFICATE_PINNING')
        },
        'analytics': {
            'firebase_analytics': b('FIREBASE_ANALYTICS'),
            'crashlytics': b('CRASHLYTICS'),
            'mixpanel': None
        },
        'testing': {
            'unit': j('TEST_UNIT', []),
            'ui': j('TEST_UI', []),
            'coverage': s('COVERAGE_TOOL'),
            'coverage_minimum': s('COVERAGE_MIN')
        },
        'build_tools': {
            'dependency_injection_kapt': False,
            'ksp': b('KSP'),
            'hilt_plugin': b('HILT_PLUGIN'),
            'build_config': b('BUILD_CONFIG', True),
            'view_binding': b('VIEW_BINDING')
        },
        'other': {
            'dagger': s('DI_FRAMEWORK') if s('DI_FRAMEWORK') == 'dagger' else None,
            'koin': s('DI_FRAMEWORK') if s('DI_FRAMEWORK') == 'koin' else None,
            'timber': b('TIMBER'),
            'leakcanary': b('LEAKCANARY'),
            'chucker': b('CHUCKER'),
            'three_ten_abp': False,
            'desugar_jdk': b('DESUGAR')
        }
    },
    'architecture': {
        'pattern': s('ARCH_PATTERN', 'unknown'),
        'layers': j('ARCH_LAYERS', []),
        'presentation_pattern': s('PRESENTATION_PATTERN'),
        'state_management': s('STATE_MANAGEMENT'),
        'navigation_type': s('NAVIGATION_TYPE'),
        'module_type': s('MODULE_TYPE', 'single-module'),
        'di_scope': s('DI_SCOPE')
    },
    'components': {
        'custom_views': j('CUSTOM_VIEWS', []),
        'custom_composables': j('CUSTOM_COMPOSABLES', []),
        'base_classes': j('BASE_CLASSES', []),
        'repositories': j('REPOSITORIES', [])
    },
    'conventions': {
        'naming': {
            'viewmodel_suffix': s('VM_SUFFIX', 'ViewModel'),
            'repository_impl_suffix': s('REPO_IMPL_SUFFIX', 'RepositoryImpl'),
            'use_case_prefix': s('USE_CASE_PREFIX'),
            'fragment_suffix': None,
            'activity_suffix': None,
            'composable_suffix': s('COMPOSABLE_SUFFIX', 'Screen'),
            'test_suffix': 'Test',
            'instrumented_test_suffix': 'InstrumentedTest'
        },
        'structure': {
            'package_by_feature': b('PACKAGE_BY_FEATURE'),
            'res_prefix': None,
            'test_mirror_package': b('TEST_MIRROR_PACKAGE')
        },
        'patterns': {
            'sealed_result': b('SEALED_RESULT'),
            'result_wrapper': None,
            'use_cases': b('USE_CASES'),
            'repository_interface': b('REPO_INTERFACE'),
            'mapper_pattern': b('MAPPER_PATTERN')
        }
    },
    'resources': {
        'themes': j('THEMES', []),
        'icon_set': s('ICON_SET'),
        'fonts': j('FONTS', []),
        'drawables_count': n('DRAWABLES_COUNT', 0),
        'vector_drawables_count': n('VECTOR_DRAWABLES_COUNT', 0),
        'localized_locales': j('LOCALES', [])
    },
    'build': {
        'flavors': j('FLAVORS', []),
        'build_types': j('BUILD_TYPES', []),
        'minification_enabled': b('MINIFICATION'),
        'shrink_resources': b('SHRINK_RESOURCES'),
        'proguard_files': j('PROGUARD_FILES', []),
        'version_catalog': b('VERSION_CATALOG_USED')
    }
}

print(json.dumps(data, indent=2, ensure_ascii=False))
