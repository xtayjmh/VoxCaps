"""Pinned llama.cpp Vulkan runtime used by Windows release builds."""

from pathlib import Path


LLAMA_RUNTIME_TAG = 'b7798'
LLAMA_RUNTIME_ASSET = 'llama-b7798-bin-win-vulkan-x64.zip'
LLAMA_RUNTIME_URL = (
    'https://github.com/ggml-org/llama.cpp/releases/download/'
    f'{LLAMA_RUNTIME_TAG}/{LLAMA_RUNTIME_ASSET}'
)
LLAMA_RUNTIME_SHA256 = 'd478b7070dd12a5c64478a398352e1f880d488c4c346a8f00e7051935ef6f8e8'
LLAMA_RUNTIME_RELATIVE_DIR = Path('core/server/engines/llama/bin')
LLAMA_RUNTIME_MARKER = 'runtime-manifest.json'
REQUIRED_LLAMA_DLLS = (
    'ggml-base.dll',
    'ggml-cpu-alderlake.dll',
    'ggml-cpu-cannonlake.dll',
    'ggml-cpu-cascadelake.dll',
    'ggml-cpu-cooperlake.dll',
    'ggml-cpu-haswell.dll',
    'ggml-cpu-icelake.dll',
    'ggml-cpu-ivybridge.dll',
    'ggml-cpu-piledriver.dll',
    'ggml-cpu-sandybridge.dll',
    'ggml-cpu-sapphirerapids.dll',
    'ggml-cpu-skylakex.dll',
    'ggml-cpu-sse42.dll',
    'ggml-cpu-x64.dll',
    'ggml-cpu-zen4.dll',
    'ggml-rpc.dll',
    'ggml-vulkan.dll',
    'ggml.dll',
    'libomp140.x86_64.dll',
    'llama.dll',
    'mtmd.dll',
)
