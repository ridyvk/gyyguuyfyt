from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / 'index.html'
SERVICE_WORKER = ROOT / 'public' / 'sw-photo1.js'


class ServiceWorkerRecoveryTests(unittest.TestCase):
    def test_app_assets_are_network_first_not_cache_first(self) -> None:
        source = SERVICE_WORKER.read_text(encoding='utf-8')
        self.assertIn("kpi-scope-v5-network-first-shell", source)
        self.assertIn("const APP_ASSET_EXTENSIONS", source)
        self.assertIn("networkFirst(event.request, { cache: 'reload' })", source)
        self.assertNotIn("return cached ?? network", source)
        self.assertNotIn("'./index.html'", source)

    def test_stale_module_failure_unregisters_service_worker_once(self) -> None:
        source = INDEX.read_text(encoding='utf-8')
        self.assertIn("kpi-scope-sw-module-recovery", source)
        self.assertIn("getRegistrations()", source)
        self.assertIn("registration.unregister()", source)
        self.assertIn("Failed to fetch dynamically imported module", source)
        self.assertIn("window.location.reload()", source)


if __name__ == '__main__':
    unittest.main()
