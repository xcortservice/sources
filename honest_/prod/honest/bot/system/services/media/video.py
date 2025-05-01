from ...worker import offloaded


@offloaded
def compress(path: str, size: int):
    import subprocess

    size = int(size / (1024**2))
    command = f"ffmpeg -y -i {path} -fs {size}M -preset ultrafast {path}"
    result = subprocess.run(command, shell=True, check=True)
    if result.returncode != 0:
        raise Exception(f"Failed to compress {path}")
    return path
