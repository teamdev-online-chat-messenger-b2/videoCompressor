import subprocess
import os

def handle_manipulate_change(original_filename, dir_path, req_params):
    input_path = os.path.join(dir_path, original_filename)

    base_name = original_filename.split('.')[0]
    output_filename = f"{base_name}_processed.mp4"
    output_path = os.path.join(dir_path, output_filename)

    # パラメーターから高さと横幅を抽出
    width = req_params['width']
    height = req_params['height']

    # FFMPEGによる解像度変換コマンド
    ffmpeg_cmd = [
        'ffmpeg',
        '-y',
        '-i', input_path,
        '-vf', f'scale={width}:{height}',
        '-c:a', 'copy',
        '-preset', 'fast',
        output_path
    ]

    print("FFMPEG実行中")

    # SubprocessでFFMPEGコマンドを実行
    result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise Exception(f"FFMPEG エラー: {result.stderr}")

    return output_filename
