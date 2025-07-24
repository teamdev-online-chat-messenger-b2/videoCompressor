import socket
import sys
import os
import json

def protocol_header(json_size, mediatype_size, payload_size):
    return  json_size.to_bytes(2, "big") + mediatype_size.to_bytes(1,"big") + payload_size.to_bytes(5,"big")

def show_menu():
    menu = {
        1: "動画ファイルの圧縮",
        2: "動画の解像度の変更", 
        3: "動画のアスペクト比の変更",
        4: "動画をオーディオに変換",
        5: "時間範囲での GIF と WEBM の作成"
    }
    
    print("=== 動画処理メニュー ===")
    for key, value in menu.items():
        print(f"{key} {value}")
    print("========================")
    return menu

def get_user_choice(menu):
    while True:
        try:
            action = int(input("メニューから処理を選択してください: "))
            if action in menu:
                return action
            else:
                print("メニュー内の数字を入力して下さい")
        except ValueError:
            print("正しい数字を入力してください")

with open('config.json', 'r', encoding='utf-8') as f:
    config = json.load(f)
    server_address = config['server_address']
    server_port = config['server_port']
    stream_rate = config['stream_rate']

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
print('connecting to {}'.format(server_address, server_port))

try:
    sock.connect((server_address, server_port))
except socket.error as err:
    print(err)
    sys.exit(1)

try:
    filepath = input('Input filePath to upload\n')
    mediatype = filepath.split('.')[-1]

    menu = show_menu()
    action = get_user_choice(menu)
    req_params = {'action':action}

    # バイナリモードでファイルを読み込む
    with open(filepath, 'rb') as f:
        # ファイルの末尾に移動し、tellは開いているファイルの現在位置を返します。ファイルのサイズを取得するために使用します
        f.seek(0, os.SEEK_END)
        filesize = f.tell()
        f.seek(0,0)

        if filesize > pow(2,40):
            raise Exception('file have to be below 1TB')

        # protocol_header()関数を用いてヘッダ情報を作成し、ヘッダとファイル名をサーバに送信します。
        # JSONサイズ（2バイト）、メディアタイプサイズ（1バイト）、ペイロードサイズ（5バイト）
        header = protocol_header(len(req_params), len(mediatype), filesize)
        print(header)

        # ヘッダの送信
        sock.send(header)

        # 一度に1400バイトずつ読み出し、送信することにより、ファイルを送信します。Readは読み込んだビットを返します
        data = f.read(stream_rate)
        while data:
            print("Sending...")
            sock.send(data)
            data = f.read(stream_rate)

except FileNotFoundError as nofile_err:
    print('inputFile not found')

except Exception as e:
    print('Error: ' + str(e))

finally:
    print('closing socket')
    sock.close()