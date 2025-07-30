import socket
import sys
import os
import json
from datetime import datetime

# 共通のコネククション関連の関数はここから実装
class CheckBeforeSend():
    @staticmethod
    def check_file_exists(filepath):
        if not os.path.exists(filepath):
            print('ファイルが存在しません')
            sys.exit(1)

    @staticmethod
    def check_file_size(filesize):
        if filesize > pow(2,40):
            print('処理対象の動画ファイルは1TB以下です。')
            sys.exit(1)
        if filesize == 0:
            print('空のファイルです。')
            sys.exit(1)

# 共通のコネククション関連の関数はここから実装
def connect_to_server(config):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        sock.connect((config['server_address'], config['server_port']))
        print('サーバーに接続しました。')
        return sock

    except socket.error as err:
        print(err)
        sys.exit(1)

def get_file_input():
    filepath = input('処理対象の動画ファイルパスを入力してください：')
    CheckBeforeSend.check_file_exists(filepath)

    return filepath

def get_request_parameters():
    menu = show_menu()
    action = get_user_choice(menu)

    match action:
        case 1:
            #動画ファイルの圧縮
            req_params = {'action': action}
        case 2:
            #動画の解像度の変更
            chosen_resolution = get_resolution_choice()
            req_params = {
                'action': action,
                'resolution': chosen_resolution
            }
        case 3:
            #動画のアスペクト比の変更
            chosen_aspect_ration = get_aspect_ratio_choice()
            req_params = {
                'action': action,
                'aspect_ratio': chosen_aspect_ration
            }
        case 4:
            #動画をオーディオに変換
            req_params = {'action': action}
        case 5:
            #時間範囲での GIF と WEBM の作成
            startseconds, endseconds = get_start_end_seconds()
            chosen_extension = get_gif_webm_choice()
            req_params = {
                'action': action,
                'startseconds': startseconds,
                'endseconds': endseconds,
                'extension': chosen_extension
            }
        case _:
            req_params = {'action': action}

    return action, req_params

def create_request_header(json_size, mediatype_size, payload_size):
    return  json_size.to_bytes(2, 'big') + mediatype_size.to_bytes(1,'big') + payload_size.to_bytes(5,'big')

def send_file_data(config, sock, filepath, req_params):
    mediatype = filepath.split('.')[-1]

    # バイナリモードでファイルを読み込む
    with open(filepath, 'rb') as f:
        f.seek(0, os.SEEK_END)
        filesize = f.tell()
        f.seek(0, 0)
        CheckBeforeSend.check_file_size(filesize)

        # create_request_header()関数を用いてヘッダ情報を作成し、ヘッダとファイル名をサーバに送信します。
        # JSONサイズ（2バイト）、メディアタイプサイズ（1バイト）、ペイロードサイズ（5バイト）
        req_params_size = len(json.dumps(req_params))
        header = create_request_header(req_params_size, len(mediatype), filesize)

        # ヘッダの送信
        sock.send(header)
        # req_params(json)および、メディアタイプ(mp3など)の送信
        sock.send(json.dumps(req_params).encode('utf-8'))
        sock.send(mediatype.encode('utf-8'))

        # 一度に1400バイトずつ読み出し、送信することにより、ファイルを送信します。Readは読み込んだビットを返します
        while True:
            data = f.read(config['stream_rate'])
            if not data:
                break
            sock.send(data)

        print("ファイル送信完了")

def upload_file(config, sock):
    filepath = get_file_input()
    action, req_params = get_request_parameters()

    try:
        send_file_data(config, sock, filepath, req_params)

        try:
            status, response_body = receive_response(sock)

            if status == 'error':
                print(f"サーバーエラー：{response_body}")
            else:
                print("処理成功！")
                save_processed_file(response_body, action)

        except Exception as recv_error:
            print(f"レスポンス受信エラー: {str(recv_error)}")

    except Exception as e:
        print(f'ファイル送信エラー: {str(e)}')

def receive_response(sock):
    responce_code = sock.recv(1)
    if responce_code == b'\x00':
        # エラーの場合
        error_size = int.from_bytes(sock.recv(4), 'big')

        error_bytes = sock.recv(error_size)
        error_text = error_bytes.decode('utf-8')

        return 'error', error_text
    else:
        # 成功の場合
        file_size = int.from_bytes(sock.recv(8), 'big')

        file_data = b''
        remaining = file_size
        while remaining > 0:
            chunk = sock.recv(min(1400, remaining))
            if not chunk:
                break
            file_data += chunk
            remaining -= len(chunk)

        return 'success', file_data


def save_processed_file(file_data):
    output_filename = input('処理後の動画を保存するファイル名（拡張子含む）を入力してください\n')

    if isinstance(file_data, bytes):
        with open(output_filename, 'wb') as f:
            f.write(file_data)

        print("処理後の動画を保存完了！")
    else:
        print("保存不可なデータ形式")

# メニューに関連した関数はここから実装
def show_menu():
    menu = {
        1: '動画ファイルの圧縮',
        2: '動画の解像度の変更',
        3: '動画のアスペクト比の変更',
        4: '動画をオーディオに変換',
        5: '時間範囲での GIF と WEBM の作成'
    }

    print('------動画処理メニュー------')
    for key, value in menu.items():
        print(f'{key} {value}')
    print("-------------------------")

    return menu

def get_user_choice(menu):
    while True:
        try:
            action = int(input('メニューから処理を選択してください: '))

            if action in menu:
                return action
            else:
                print('メニュー内の数字を入力して下さい')

        except ValueError:
            print('正しい数字を入力してください')

# その他必要な関数はここから実装
def load_client_config():
    with open('config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)

    return {
        'server_address': config['server_address'],
        'server_port': config['server_port'],
        'stream_rate': config['stream_rate']
    }

# 機能別の関数はここから実装
def get_resolution_choice():
    resolution_choices = {
        1: ("480p", 854, 480),
        2: ("720p", 1280, 720),
        3: ("1080p", 1920, 1080),
        4: ("1440p", 2560, 1440),
        5: ("4K", 3840, 2160)
    }

    print("-------解像度リスト-------")
    for choice, (resolution_name, width, height) in resolution_choices.items():
        print(f"{choice}. {resolution_name} ({width} * {height})")
    print("------------------------")

    while True:
        try:
            user_choice = int(input("解像度を選択してください: "))
            if user_choice in resolution_choices:
                return resolution_choices[user_choice][0]
            else:
                print("１から５の中から選択してください")

        except ValueError:
            print("正しい数字を入力してください")

def get_start_end_seconds():
     
     while True:
        try:
            # 切り取る開始時間~終了時間を取得する
            starttime_str = input("開始時刻（HH:MM:SS）を入力してください: ")
            starttime_obj = datetime.strptime(starttime_str, "%H:%M:%S")
            endtime_str = input("終了時刻（HH:MM:SS）を入力してください: ")
            endtime_obj = datetime.strptime(endtime_str, "%H:%M:%S")
            startseconds = starttime_obj.hour * 3600 + starttime_obj.minute * 60 + starttime_obj.second
            endseconds = endtime_obj.hour * 3600 + endtime_obj.minute * 60 + endtime_obj.second

            if startseconds <= endseconds:
                return startseconds, endseconds
            else:
                print("終了時刻は、開始時間より後にしてください")

        except ValueError:
            print("正しい数字を入力してください")
    
def get_gif_webm_choice():
    # GIFとWEBMの選択
    gif_webm_choices = {
        1: "GIF",
        2: "WEBM"
    }
    print("-------以下の形式から選んで下さい-------")
    for choice, extension in gif_webm_choices.items():
        print(f"{choice}. {extension}")
    print("------------------------")

    while True:

        try:
            user_choise = int(input('希望の形式を選んでください'))
            if user_choise in gif_webm_choices:
                return gif_webm_choices[user_choise].lower()
            else:
                print("正しい選択肢を選んでください")
        
        except ValueError:
            print('正しい数字を入力してください')
    
def get_aspect_ratio_choice():
    aspect_ratio_choices = {
        # key : (aspect_ratio, description)
        1: ('4:3', '昔の映像などに使用'),
        2: ('16:9', 'テレビ・配信動画用')
    }
    print('変更可能なアスペクト比リスト')
    for choise, (aspect_ratio, description) in aspect_ratio_choices.items():
        print(f'{choise}. {aspect_ratio} {description}')
    print('------------------------')

    while True:
        try:
            user_choise = int(input("変更したいアスペクト比を選択してください: "))
            if user_choise in aspect_ratio_choices:
                return aspect_ratio_choices[user_choise][0]
            else:
                print('リストの中の数字から選択してください')

        except Exception as e:
            print(f'エラー：{str(e)}')

def main():
    config = load_client_config()

    sock = connect_to_server(config)

    try:
        upload_file(config, sock)

    except Exception as error:
        print('エラー: ' + str(error))

    finally:
        print('ソケットを閉じます')
        sock.close()

if __name__ == '__main__':
    main()
