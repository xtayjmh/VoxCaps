import builtins
import importlib.util
import sys
import types
import unittest
from contextlib import nullcontext
from enum import Enum, auto
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


class _Capabilities(Enum):
    ASR = auto()
    PUNC = auto()
    TIMESTAMPS = auto()
    HOTWORDS = auto()


class _QwenLikeEngine:
    capabilities = [
        _Capabilities.ASR,
        _Capabilities.PUNC,
        _Capabilities.TIMESTAMPS,
    ]


def _module(name, **attributes):
    module = types.ModuleType(name)
    module.__dict__.update(attributes)
    return module


def load_model_loader():
    engine = _QwenLikeEngine()
    config = types.SimpleNamespace(
        model_type='qwen_asr',
        hotwords_path=ROOT / 'missing-hotwords.txt',
        aligner_idle_timeout=10,
    )
    factory = types.SimpleNamespace(create_asr_engine=lambda model_type: engine)
    logger = types.SimpleNamespace(info=lambda *args: None, error=lambda *args, **kwargs: None)

    packages = {
        'core': _module('core'),
        'core.server': _module('core.server'),
        'core.server.worker': _module('core.server.worker', logger=logger),
        'core.server.engines': _module('core.server.engines'),
        'core.server.state': _module(
            'core.server.state',
            console=types.SimpleNamespace(status=lambda *args, **kwargs: nullcontext()),
        ),
        'core.server.engines.factory': _module(
            'core.server.engines.factory',
            EngineFactory=factory,
        ),
        'core.server.engines.base': _module(
            'core.server.engines.base',
            EngineCapabilities=_Capabilities,
        ),
        'config_server': _module(
            'config_server',
            ServerConfig=config,
            ModelPaths=types.SimpleNamespace(),
        ),
    }
    for name in ('core', 'core.server', 'core.server.worker', 'core.server.engines'):
        packages[name].__path__ = []

    module_name = 'core.server.worker.model_loader_under_test'
    spec = importlib.util.spec_from_file_location(
        module_name,
        ROOT / 'core/server/worker/model_loader.py',
    )
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, packages):
        spec.loader.exec_module(module)
    return module, engine


class ModelLoaderOptionalSherpaTests(unittest.TestCase):
    def test_qwen_path_does_not_import_sherpa_onnx(self):
        module, engine = load_model_loader()
        original_import = builtins.__import__

        def reject_sherpa(name, *args, **kwargs):
            if name == 'sherpa_onnx':
                raise AssertionError('Qwen startup must not require sherpa_onnx')
            return original_import(name, *args, **kwargs)

        with patch('builtins.__import__', side_effect=reject_sherpa):
            loader = module.ModelLoader()
            loader.load()

        self.assertIs(loader.recognizer, engine)


if __name__ == '__main__':
    unittest.main()
