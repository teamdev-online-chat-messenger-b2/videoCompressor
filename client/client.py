import socket
import sys
import os
import json

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


def protocol_header(json_size, mediatype_size, payload_size):
    return  json_size.to_bytes(2, 'big') + mediatype_size.to_bytes(1,'big') + payload_size.to_bytes(5,'big')

def show_menu():
    menu = {
        1: '動画ファイルの圧縮',
        2: '動画の解像度の変更',
        3: '動画のアスペクト比の変更',
        4: '動画をオーディオに変換',
        5: '時間範囲での GIF と WEBM の作成'
    }

    print('=== 動画処理メニュー ===')
    for key, value in menu.items():
        print(f'{key} {value}')
    print('========================')
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
            user_choice = int(input("お望みの解像度を選択してください: "))
            if user_choice in resolution_choices:
                return resolution_choices[user_choice][1], resolution_choices[user_choice][2]
            else:
                print("１から５の中から選んでください")
        except ValueError:
            print("正しい数字を入力してください")

def main():
    with open('config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
        server_address = config['server_address']
        server_port = config['server_port']
        stream_rate = config['stream_rate']
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    print('サーバーに接続します。')

    try:
        sock.connect((server_address, server_port))
    except socket.error as err:
        print(err)
        sys.exit(1)

    try:
        filepath = input('処理対象の動画ファイルパスを入力してください\n')
        CheckBeforeSend.check_file_exists(filepath)

        mediatype = filepath.split('.')[-1]

        menu = show_menu()
        action = get_user_choice(menu)
        req_params = {'action':action}

        # バイナリモードでファイルを読み込む
        with open(filepath, 'rb') as f:
            f.seek(0, os.SEEK_END)
            filesize = f.tell()
            f.seek(0,0)

            CheckBeforeSend.check_file_size(filesize)

            # protocol_header()関数を用いてヘッダ情報を作成し、ヘッダとファイル名をサーバに送信します。
            # JSONサイズ（2バイト）、メディアタイプサイズ（1バイト）、ペイロードサイズ（5バイト）
            req_params_size = len(json.dumps(req_params))
            header = protocol_header(req_params_size, len(mediatype), filesize)

            # serverへのデータ送信および、serverからのレスポンスは内側のtry-catchで制御
            try:
                # ヘッダの送信
                sock.send(header)
                # req_params(json)および、メディアタイプ(mp3など)の送信
                sock.send(json.dumps(req_params).encode('utf-8'))
                sock.send(mediatype.encode('utf-8'))

                # 一度に1400バイトずつ読み出し、送信することにより、ファイルを送信します。Readは読み込んだビットを返します
                data = f.read(stream_rate)
                while data:
                    sock.send(data)
                    data = f.read(stream_rate)

            except Exception as e:
                print('エラー: ' + str(e))

            finally:
                err_response = sock.recv(4096)
                if err_response:
                    response_json = err_response.decode('utf-8')
                    print(f'サーバーからのレスポンス:{response_json}')
                else:
                    print('成功')

    except Exception as e:
        print('エラー: ' + str(e))

    finally:
        print('ソケットを閉じます')
        sock.close()

if __name__ == '__main__':
    main()
