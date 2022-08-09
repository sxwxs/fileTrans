#!/usr/bin/python3

__author__ = 'sxwxs'
__date__ = '2022-08-09'

import os
import sys
import time
import queue
import socket
import hashlib
import argparse
import threading

UNIT_SIZE = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
UNIT_TIME = ['s', 'min', 'h', 'd', 'm', 'y']
UNIT_TIME_SCALE = [60, 60, 24, 30, 12]
HASH_CHUNK_SIZE = 1024 * 1024 * 5 # 5 MB
TRANSFER_CHUNK_SIZE = 1024 * 1024 * 5 # 5 MB
HASH_LOG = False

def read_line(c):
    data = b''
    while True:
        ch = c.recv(1)
        if not ch or ch == b'\n':
            return data
        data += ch

def send_line(s, d):
    if type(d) != bytes:
        d = str(d).encode('utf8')
    assert b'\n' not in d
    s.send(d + b'\n')

def get_size_str(size):
    i = 0
    while size > 1024 and i < len(UNIT_SIZE):
        size /= 1024
        i += 1
    return '%.2f %s' % (size, UNIT_SIZE[i])

def get_time_str(t):
    i = 0
    r = ''
    t = int(t)
    while t > 0 and i < len(UNIT_TIME_SCALE):
        res = t % UNIT_TIME_SCALE[i]
        if res > 0:
            r = ' %d %s' % (res, UNIT_TIME[i]) + r
        t //= UNIT_TIME_SCALE[i]
        i += 1
    if t > 0:
        r = '%d %s' % (t, UNIT_TIME[i]) + r
    return r.strip()

def cur_time_str():
    return time.strftime("%Y-%m-%d-%H_%M_%S", time.localtime())

def warning(msg):
    print('#' * 32)
    print('Warning.')
    print(msg)
    print('#' * 32)

def send_file(s, filename):
    try:
        file_size = os.path.getsize(filename)
    except FileNotFoundError:
        send_line(s, b'-1')
        return
    send_line(s, file_size)
    mode = read_line(s)
    if mode == b'CHECK':
        exist_file_size = int(read_line(s).decode('utf8'))
        exist_file_size_str = get_size_str(exist_file_size)
        myhash = hashlib.md5()
        with open(filename, 'rb') as f:
            q = queue.Queue()
            validated_size = [0]
            validated_flag = [True]
            def sync_hash_with_client():
                while True:
                    h, size = q.get()
                    if not h:
                        assert size == 0
                        break
                    rhash = read_line(s).decode('utf8')
                    if rhash == h:
                        send_line(s, b'0')
                        validated_size[0] += size
                    else:
                        # mismatch, stop calculate hash
                        validated_flag[0] = False
                        send_line(s, b'1')
                        break
            t = threading.Thread(target=sync_hash_with_client)
            t.start()
            hashed_size = 0
            bt = time.time()
            try:
                with open('%s.hashlog' % filename, 'r') as hlog:
                    lsz = 0
                    for l in hlog:
                        sz, hashx = l.strip().split('\t')
                        sz = int(sz)
                        q.put((hashx, sz - lsz))
                        lsz = sz
                print('Using hash log file:', '%s.hashlog' % filename, 'skip size:', get_size_str(sz))
                hashed_size = sz
                f.seek(sz)
            except FileNotFoundError:
                pass
            if HASH_LOG:
                hlogf = open('%s.hashlog' % filename, 'a')
            while validated_flag[0] and hashed_size < exist_file_size:
                if HASH_CHUNK_SIZE < exist_file_size - hashed_size:
                    l = f.read(HASH_CHUNK_SIZE)
                else:
                    l = f.read(exist_file_size - hashed_size)
                et = time.time() - bt
                sys.stdout.write("\rHash: %s/%s, %.2f %%.  Vaildate: %.2f %%. %s elasped" % (get_size_str(hashed_size), exist_file_size_str, hashed_size/exist_file_size*100, validated_size[0]/exist_file_size*100, get_time_str(et)))
                sys.stdout.flush()
                if not l:
                    break
                hashed_size += len(l)
                myhash.update(l)
                hashx = myhash.hexdigest()
                q.put((hashx, len(l)))
                if HASH_LOG:
                    if hashed_size % HASH_CHUNK_SIZE == 0:
                        hlogf.write('%d\t%s\n' % (hashed_size, hashx))
            print()
            print('Hash done.', myhash.hexdigest())
            q.put(('', 0))
            if HASH_LOG:
                f.close()
            
        t.join()
        if not validated_flag[0]:
            warning('Hash mismatch. %s validated' % get_size_str(validated_size[0]))
            overwrite = input('Do you want to overwrite the existed data that does match with remove file? (y/n)')
            if overwrite != 'y':
                return
        else:
            print('All exist data validated.')
        exist_file_size = validated_size[0]
        mode = read_line(s)
    else:
        exist_file_size = 0
    if mode == b'START':
        rexist_file_size = int(read_line(s).decode('utf8'))
        assert rexist_file_size == exist_file_size
        if exist_file_size == file_size:
            print('Remote files are identical to local files, no transfer required.')
            print('Stop')
            return
        send_size = 0
        with open(filename, 'rb') as f:
            f.seek(exist_file_size)
            bt = time.time()
            lt = bt
            while exist_file_size + send_size < file_size:
                data = f.read(TRANSFER_CHUNK_SIZE)
                s.send(data)
                ds = len(data)
                send_size += ds
                ct = time.time()
                et = ct - bt
                speed = ds/(ct - lt)
                sys.stdout.write('\r%s sent, %s elasped, %s/s, %s/s. %.2f %%. %s remainded' % (get_size_str(send_size), get_time_str(et), get_size_str(send_size/et), get_size_str(speed), (exist_file_size + send_size)/file_size*100, get_time_str((file_size-exist_file_size-send_size)/speed)))
                sys.stdout.flush()            
                lt = ct
            print()
    print('Finished')

def server_worker(s, address):
    mode = read_line(s)
    if mode == b'GET':
        filename = read_line(s).decode('utf8')
        send_file(s, filename)
    elif mode == b'PUT':
        filename = read_line(s).decode('utf8')
        total_size = int(read_line(s).decode('utf8'))
        get_file(s, filename, total_size)

def server_main(port, target, key):
    s = socket.socket()
    address = '0.0.0.0'
    s.bind((address, port))
    s.listen(1)
    print('Start server at %s:%d' % (address, port))
    print('Secret Key:', key)
    while True:
        c, a = s.accept()
        print(cur_time_str(), 'Accept:', a)
        client_key = read_line(c).decode('utf8')
        if client_key == key:
            print('Client key ok')
            send_line(c, b'0')
            server_worker(c, a)
            c.close()
        else:
            print('Bad client key, connection close.', a)
            send_line(c, b'1')
            c.close()

def get_file(s, local_filename, total_size):
    if total_size > 0:
        total_size_str = get_size_str(total_size)
        print('Remote file size:', total_size_str)
    else:
        print('Error! Remote file not found')
        return
    try:
        exist_file_size = os.path.getsize(local_filename)
        exist_file_size_str = get_size_str(exist_file_size)
        print('Found exist file, size:', exist_file_size_str)
        if exist_file_size > total_size:
            warning('Local file size is larger than remote file size')
            if input('Do you want to continue? (y/n)') != 'y':
                return
        print('Chicking ...')
        # set CHECK mode
        send_line(s, 'CHECK')
        send_line(s, exist_file_size)
        ######
        myhash = hashlib.md5()
        with open(local_filename, 'rb') as f:
            q = queue.Queue()
            validated_size = [0]
            validated_flag = [True]
            def sync_hash_with_server():
                if HASH_LOG:
                    f = open('%s.hashlog' % local_filename, 'w')
                while True:
                    h, size = q.get()
                    if not h:
                        assert size == 0
                        break
                    send_line(s, h)
                    r = read_line(s)
                    if r == b'0':
                        validated_size[0] += size
                        if HASH_LOG:
                            if validated_size[0] % HASH_CHUNK_SIZE == 0:
                                f.write('%d\t%s\n' % (validated_size[0], h))
                    else:
                        # mismatch, stop calculate hash
                        validated_flag[0] = False
                        break
                if HASH_LOG:
                    f.close()
            t = threading.Thread(target=sync_hash_with_server)
            hashed_size = 0
            try:
                with open('%s.hashlog' % local_filename, 'r') as hlog:
                    lsz = 0
                    for l in hlog:
                        sz, hashx = l.strip().split('\t')
                        sz = int(sz)
                        q.put((hashx, sz - lsz))
                        lsz = sz
                print('Using hash log file:', '%s.hashlog' % local_filename, 'skip size:', get_size_str(sz))
                hashed_size = sz
                f.seek(sz)
            except FileNotFoundError:
                pass
            t.start()
            bt = time.time()
            while validated_flag[0]:
                l = f.read(HASH_CHUNK_SIZE)
                et = time.time() - bt
                sys.stdout.write("\rHash: %s/%s, %.2f %%.  Vaildate: %.2f %%. %s elasped" % (get_size_str(hashed_size), exist_file_size_str, hashed_size/exist_file_size*100, validated_size[0]/exist_file_size*100, get_time_str(et)))
                sys.stdout.flush()
                if not l:
                    q.put(('', 0))
                    break
                hashed_size += len(l)
                myhash.update(l)
                hashx = myhash.hexdigest()
                q.put((hashx, len(l)))
            print()
            print('Hash done.', myhash.hexdigest())
        t.join()
        if not validated_flag[0]:
            warning('Hash mismatch. %s validated' % get_size_str(validated_size[0]))
            overwrite = input('Do you want to overwrite the existed data that does match with remove file? (y/n)')
            if overwrite != 'y':
                return
        else:
            print('All exist data validated.')
        exist_file_size = validated_size[0]
    except FileNotFoundError:
        exist_file_size = 0
    # start
    send_line(s, 'START')
    send_line(s, exist_file_size)
    ######
    cur_size = exist_file_size
    recv_size = 0
    if cur_size == total_size:
        print('Local files are identical to remote files, no transfer required.')
        print('Stop')
        return
    def recv_and_write(s, f, cur_size, recv_size, total_size):
        bt = time.time()
        lt = bt
        cds = 0
        while cur_size + recv_size <= total_size:
            data = s.recv(TRANSFER_CHUNK_SIZE)
            #hashv = recv_x(s, hash_len)
            #try:
            #    hashv = hashv.decode('utf8')
            #except UnicodeDecodeError:
            #    print (hashv, len(hashv))
            #hasho.update(data)
            #if hashv == hasho.hexdigest():
            ds = len(data)
            if ds == 0:
                print('Error, connection closed!')
                return
            recv_size += ds
            cds += ds
            if f.write(data) == ds:
                pass
            else:
                raise Exception('file write error')
            if cds >= TRANSFER_CHUNK_SIZE:
                ct = time.time()
                et = ct - bt
                speed = cds/(ct - lt)
                sys.stdout.write('\r%s recived, %s elasped, %s/s, %s/s. %.2f %%. %s remainded' % (get_size_str(recv_size), get_time_str(et), get_size_str(recv_size/et), get_size_str(speed), recv_size/(total_size-cur_size)*100,get_time_str((total_size-cur_size-recv_size)/speed)))
                sys.stdout.flush()            
                lt = ct
                cds = 0

    if exist_file_size > 0:
        # https://es2q.com/blog/2019/02/22/modify_file_without_rewrite/
        with open(local_filename, 'rb+') as f:
            f.seek(exist_file_size)
            recv_and_write(s, f, cur_size, recv_size, total_size)
    else:
        with open(local_filename, 'wb') as f:
            recv_and_write(s, f, cur_size, recv_size, total_size)
    print('Finished')

def client_worker(s, remote_filename, local_filename, mode):
    if mode == 'get':
        # set GET mode
        send_line(s, 'GET')
        send_line(s, remote_filename)
        ######
        total_size = int(read_line(s).decode('utf8'))
        get_file(s, local_filename, total_size)
    elif mode == 'put':
        send_line(s, 'PUT')
        send_line(s, remote_filename)
        send_file(s, local_filename)

def client_main(address, port, key, filename, mode):
    s = socket.socket()
    s.connect((address, port))
    send_line(s, key)
    if read_line(s) == b'0':
        print('Connected')
    else:
        print('Bad key')
        return
    if not filename:
        while True:
            filename = input('Input File Name')
            if not filename:
                break
            client_worker(s, filename, filename)
    else:
        client_worker(s, filename, filename, mode)
        

def main():
    global HASH_LOG
    parser = argparse.ArgumentParser(description='Transferring Files via Network')
    parser.add_argument('-a', type=str, metavar='Remote address', help='Remote address, works as server when not specified', default='')
    parser.add_argument('-p', type=int, metavar="Port", help='Port for connect or listen to', default='14605')
    parser.add_argument('-f', type=str, metavar="Target file (or Dir)", help='Path to target file / dir', default='')
    parser.add_argument('-k', type=str, metavar="Secret key", help='Secret key', default='')
    parser.add_argument('-m', type=str, metavar="mode", help='get / put / ls', default='get')
    parser.add_argument('--hashlog', action='store_true', help='Write hash to log')
    args = parser.parse_args()
    print(args)
    HASH_LOG = args.hashlog
    if args.a == '':
        server_main(args.p, args.f, args.k)
    else:
        client_main(args.a, args.p, args.k, args.f, args.m)


if __name__ == '__main__':
    main()