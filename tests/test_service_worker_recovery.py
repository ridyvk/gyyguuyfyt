from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / 'index.html'
PHOTO_SERVICE_WORKER = ROOT / 'public' / 'sw-photo1.js'
LEGACY_SERVICE_WORKER = ROOT / 'public' / 'sw.js'
MAIN = ROOT / 'src' / 'main.tsx'


class ServiceWorkerRecoveryTests(unittest.TestCase):
    def assert_network_first_service_worker(self, path: Path) -> None:
        source = path.read_text(encoding='utf-8')
        self.assertIn("kpi-scope-v6-network-first-recovery", source)
        self.assertIn("const APP_ASSET_EXTENSIONS", source)
        self.assertIn("networkFirst(event.request, { cache: 'reload' })", source)
        self.assertIn("keys.map((key) => caches.delete(key))", source)
        self.assertNotIn("return cached ?? network", source)
        self.assertNotIn("'./index.html'", source)

    def test_app_assets_are_network_first_not_cache_first(self) -> None:
        self.assert_network_first_service_worker(PHOTO_SERVICE_WORKER)
        self.assert_network_first_service_worker(LEGACY_SERVICE_WORKER)

    def test_stale_module_failure_unregisters_service_worker_once(self) -> None:
        source = INDEX.read_text(encoding='utf-8')
        self.assertIn("kpi-scope-sw-module-recovery", source)
        self.assertIn("getRegistrations()", source)
        self.assertIn("registration.unregister()", source)
        self.assertIn("Failed to fetch dynamically imported module", source)
        self.assertIn("error loading dynamically imported module", source)
        self.assertIn("window.location.replace", source)
        self.assertLess(source.index("kpi-scope-sw-module-recovery"), source.index('/src/main.tsx'))

    def test_no_service_worker_recovery_mode_is_not_reregistered(self) -> None:
        index_source = INDEX.read_text(encoding='utf-8')
        main_source = MAIN.read_text(encoding='utf-8')
        self.assertIn("has('no-sw')", index_source)
        self.assertIn("has('no-sw')", main_source)
        self.assertIn("!serviceWorkerDisabled", main_source)
        self.assertIn("__KPI_SCOPE_RECOVER__", main_source)


if __name__ == '__main__':
    unittest.main()
