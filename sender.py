# run sender by python3 sender.py -p <port> -g <requester port> -r <rate> -q <seq_no> -l <length>

from datetime import datetime
import argparse
import socket
import struct
import time
import os


def main():
    # Define argument parser
    parser = argparse.ArgumentParser(
        description='Process command line arguments.')

    # Define required arguments
    parser.add_argument('-p', required=True, help='port')
    parser.add_argument('-g', required=True, help='requester port')
    parser.add_argument('-r', required=True, help='rate')
    parser.add_argument('-q', required=True, help='sequence number')
    parser.add_argument('-l', required=True, help='length')
    parser.add_argument('-f', required=True, help='host name of emulator')
    parser.add_argument('-e', required=True, help='port of the emulator')
    parser.add_argument('-i', required=True, help='priority')
    parser.add_argument('-t', required=True, help='timeout')

    # Parse the arguments and check for incorrect input
    args = parser.parse_args()
    try:
        port = int(args.p)
        req_port = int(args.g)
        rate = int(args.r)
        seq_no = 1
        length = int(args.l)
        emulator_host = args.f
        emulator_port = int(args.e)
        priority = int(args.i)
        timeout = int(args.t)

    except ValueError:
        print('All arguments must be an integer, no strings')
        return

    UDP_IP = socket.gethostbyname(socket.gethostname())

    # listen for a request to send
    sock_listener = socket.socket(socket.AF_INET,  # Internet
                                  socket.SOCK_DGRAM)  # UDP
    sock_listener.bind((UDP_IP, port))
    sock_listener.settimeout(30.0)

    file_name = ''
    requester_ip = ''
    while True:
        data, addr = sock_listener.recvfrom(1024)  # buffer size is 1024 bytes
        requester_ip = addr[0]

        header = struct.unpack("!BIHIHIcII", data[:26])  # for lab 2
        window_size = header[8]

        file_name = data[26:].decode()  # for lab 2
        if file_name != '':
            break

    sock_listener.close()

    file_size = os.path.getsize(file_name)

    # get num of packets needed to send the entire file
    num_packets = file_size // length
    TOTAL_PACKETS = num_packets
    if file_size % length != 0:
        num_packets += 1

    # open the socket ot send on
    sock = socket.socket(socket.AF_INET,  # Internet
                         socket.SOCK_DGRAM)  # UDP
    # sock.bind((UDP_IP, req_port))
    sock.bind((requester_ip, port))
    sock.setblocking(False)
    # sock.settimeout(10.0)

    # send all packets in window

    with open(file_name, 'rb') as f:
        packet_type = 'D'
        packets_lost = 0
        print(f"# of packets: {num_packets}")
        while (num_packets > 0):
            start_time = time.time()
            window = []
            print()
            # send all packets in window
            for i in range(window_size):
                if (num_packets <= 0):
                    break

                payload = f.read(length)

                # TODO convert seq_no w htonl and vice versa
                encapsulated_packet = construct_packet(priority, UDP_IP, port, requester_ip,
                                                       req_port, packet_type.encode(), seq_no, window_size, payload)
                emulator_host_ip = socket.gethostbyname(emulator_host)

                # window = (seq#, start_time, payload, attempt#)
                window.append(
                    (seq_no, time.time() + timeout/1000, encapsulated_packet, 1))
                # window.append(
                #     (seq_no, time.time() - start_time, encapsulated_packet, 1))

                sock.sendto(
                    encapsulated_packet, (emulator_host_ip, emulator_port))
                print(f"Sent packet with seq# {seq_no}")

                seq_no += 1
                time.sleep(1 / rate)
                num_packets -= 1

            # recvfrom until timeout
            acked = set()

            # for packet in window:
            while len(acked) < window_size and time.time() < window[-1][1]:
                
                try:
                    ack, ack_addr = sock.recvfrom(1024)
                    header = struct.unpack("!BIHIHIcII", ack[:26])
                    ack_seq = header[7]
                    # if ack_seq != packet[0]: #TODO receiving out of order
                    #     print("TRUE")
                    for packet in window:
                        if packet[0] == ack_seq:
                            break
                    if time.time() > packet[1]:
                        print("givin up")
                        continue
                    acked.add(ack_seq)
                    print(f'Received ack: {ack_seq}', time.time(), packet[1], packet[0])
                    # print(len(acked), window_size, window[-1])
                except:
                    # print("TIMEOUT", time_ms/1000)
                    pass

                # elapsed_ms = (time.time() - start_time)*1000
                # packet_send_time = packet[1]*1000
                # time_ms = timeout + packet_send_time - elapsed_ms

                # # use if not all packets are sent by end of timeout TODO
                # if time_ms < 0:
                #     time_ms = 10

                # sock.settimeout(time_ms/1000)

                # try:
                #     ack, ack_addr = sock.recvfrom(1024)
                #     header = struct.unpack("!BIHIHIcII", ack[:26])
                #     ack_seq = header[7]
                #     acked.add(ack_seq)
                #     print(f'Received ack: {ack_seq}', time_ms/1000)
                # except socket.timeout:
                #     # print("TIMEOUT", time_ms/1000)
                #     pass

            # send unacked packets
            for i in range(2, 7):
                if len(acked) == window_size:
                    break

                window_length = len(window)
                # for packet in window:
                for j in range(window_length):
                    # if seq_no not in acked and ensure we don't resend previously sent packets
                    if window[j][0] not in acked and window[j][3] == i - 1:
                        encapsulated_packet = construct_packet(priority, UDP_IP, port, requester_ip,
                                                               req_port, packet_type.encode(), window[j][0], window_size, window[j][2][26:])
                        sock.sendto(encapsulated_packet,
                                    (emulator_host, emulator_port))
                        window.append(
                            (window[j][0], time.time() - start_time, encapsulated_packet, i))
                        packets_lost += 1

                        print(
                            f"SENDING UNACKED PACKET - seq_no:{window[j][0]}")

                        time.sleep(1 / rate)
                print()

                # only wait for ACKs from unacknowledged packets on ith attempt
                for packet in window:
                    if packet[0] not in acked and packet[3] == i:

                        elapsed_ms = (time.time() - start_time)*1000
                        packet_send_time = packet[1]*1000
                        time_ms = timeout + packet_send_time - elapsed_ms

                        # use if not all packets are sent by end of timeout
                        if time_ms < 0:
                            time_ms = 10

                        sock.settimeout(time_ms/1000)
                        try:
                            ack, ack_addr = sock.recvfrom(1024)
                            header = struct.unpack("!BIHIHIcII", ack[:26])
                            ack_seq = header[7]
                            acked.add(ack_seq)
                            print(f'Received ack: {ack_seq}')
                        except socket.timeout:
                            pass

            # give up on remaining unacked packets
            for packet in window:
                if packet[0] not in acked and packet[3] == 1:
                    # packets_lost += 1
                    print(
                        f"Giving up on packet with sequence number {packet[0]}: no ACK received")

        # send end packet
        packet_type = 'E'
        print("sending END packet")
        end_packet = construct_packet(priority, UDP_IP, port, requester_ip,
                                      req_port, packet_type.encode(), seq_no, 0, b'')
        bytes_sent = sock.sendto(end_packet, (emulator_host, emulator_port))
        print()
        print(
            f'Loss rate: {(packets_lost/(TOTAL_PACKETS + packets_lost))*100:.2f}%')


def construct_packet(priority, src_ip_addr, src_port, dest_ip_addr, dest_port, packet_type, sequence_num, inner_length, payload):
    header = struct.pack("!cII", packet_type, sequence_num, inner_length)
    packet_with_header = header + payload

    src_ip_int = struct.unpack("!I", socket.inet_aton(src_ip_addr))[0]
    dest_ip_int = struct.unpack("!I", socket.inet_aton(dest_ip_addr))[0]

    new_header = struct.pack("!BIHIHI", priority, src_ip_int, src_port, dest_ip_int,
                             dest_port, len(packet_with_header))
    return new_header + packet_with_header


if __name__ == "__main__":
    main()
