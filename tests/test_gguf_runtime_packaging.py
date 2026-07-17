import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_script_module(name, relative_path):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class GGufRuntimePackagingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = load_script_module(
            'voxcaps_llama_runtime_manifest',
            'scripts/llama_runtime_manifest.py',
        )
        cls.verifier = load_script_module(
            'voxcaps_package_verifier',
            'scripts/verify-windows-packages.py',
        )

    def test_missing_runtime_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, '完整包缺少 Server 运行库'):
                self.verifier.verify_full_package_root(Path(directory))

    def test_complete_shared_runtime_is_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            package_root = Path(directory)
            for relative in (
                *self.verifier.GGUF_RUNTIME_FILES,
                *self.verifier.SERVER_RUNTIME_FILES,
            ):
                path = package_root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()
            self.verifier.verify_full_package_root(package_root)

    def test_every_gguf_loader_uses_the_shared_runtime(self):
        loaders = (
            'core/server/engines/llama/llama.py',
            'core/server/engines/fun_asr_gguf/inference/llama.py',
            'core/server/engines/qwen_asr_gguf/inference/llama.py',
            'core/server/engines/force_aligner_gguf/inference/llama.py',
        )
        for relative in loaders:
            source = (ROOT / relative).read_text(encoding='utf-8')
            self.assertIn('require_llama_runtime()', source, relative)
            self.assertNotIn("Path(__file__).parent / 'bin'", source, relative)

    def test_build_pipeline_prepares_runtime_before_packaging(self):
        pipeline = (ROOT / 'scripts/build-windows-packages.ps1').read_text(
            encoding='utf-8'
        )
        prepare_index = pipeline.index('scripts/prepare-llama-runtime.py')
        build_index = pipeline.index('pyinstaller @commonArgs build.spec')
        self.assertLess(prepare_index, build_index)


if __name__ == '__main__':
    unittest.main()
