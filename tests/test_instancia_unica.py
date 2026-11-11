"""Testes de prevenção de instâncias duplicadas (não acessam dados de ensaio)."""
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

APP = Path(__file__).resolve().parent.parent / "app"
sys.path.insert(0, str(APP))
import revisao_web


class TestInstanciaUnica(unittest.TestCase):
    def run_main(self, existing, server_side_effect=None, no_open=False):
        fake_cfg = Mock()
        argv = ["revisao_web.py", "--nao-abrir"] if no_open else ["revisao_web.py"]
        with patch.object(revisao_web, "existing_editor_url", return_value=existing), \
             patch.object(revisao_web.ensaio, "load_config", return_value=fake_cfg), \
             patch.object(revisao_web.ensaio, "ensure_directories"), \
             patch.object(revisao_web, "AppState"), \
             patch.object(revisao_web, "Server", side_effect=server_side_effect) as make_server, \
             patch.object(revisao_web.webbrowser, "open") as browser, \
             patch.object(sys, "argv", argv):
            result = revisao_web.main()
            return result, make_server.call_count, browser.call_count

    def test_segundo_atalho_reutiliza_instancia(self):
        code, created, opened = self.run_main("http://127.0.0.1:8765/")
        self.assertEqual(code, 0)
        self.assertEqual(created, 0)
        self.assertEqual(opened, 1)

    def test_modo_sem_navegador_tambem_nao_duplica(self):
        code, created, opened = self.run_main("http://127.0.0.1:8765/", no_open=True)
        self.assertEqual(code, 0)
        self.assertEqual(created, 0)
        self.assertEqual(opened, 0)

    def test_porta_ocupada_nao_tenta_outras_portas(self):
        code, created, opened = self.run_main(None, OSError("porta em uso"))
        self.assertEqual(code, 2)
        self.assertEqual(created, 1)
        self.assertEqual(opened, 0)


if __name__ == "__main__":
    unittest.main()
