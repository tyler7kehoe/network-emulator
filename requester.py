import argparse
import datetime
import socket
import struct
import time
from sys import exit
from datetime import datetime


def main():
    # Define argument parser
    parser = argparse.ArgumentParser(
        description='Process command line arguments.')

    # Define required arguments
    parser.add_argument('-p', required=True, help='port')
    parser.add_argument('-o', required=True, help='file option')
    parser.add_argument('-f', required=True, help='host name of the emulator')
    parser.add_argument('-e', required=True, help='the port of the emulator')
    parser.add_argument('-w', required=True, help='the requesters window size')

    # Parse the arguments
    args = parser.parse_args()
    port = int(args.p)
    file_option = args.o
    host_name = args.f
    emulator_port = int(args.e)
    window_size = int(args.w)

    UDP_IP = socket.gethostbyname(socket.gethostname())
    UDP_PORT = port

    # read from tracker.txt
    file = open('./tracker.txt', 'r')
    tracker = []
    line = file.readline()
    while line:
        tokens = line.split()
        tracker.append(tokens)
        line = file.readline()
    tracker = sorted(tracker, key=lambda x: x[1])

    # initialize socket
    sock = socket.socket(socket.AF_INET,  # Internet
                         socket.SOCK_DGRAM)  # UDP

    sock.bind((UDP_IP, UDP_PORT))

    # set a timeout for the recvfrom() method
    sock.settimeout(10.0)

    file = open(file_option, "wb")
    packets_received = []
    packet_dict = {}

    try:
        # send request packets
        for line in tracker:
            total_packets = 0
            total_bytes = 0
            start = time.time()     # start the timer for a given file

            if file_option in line:

                encapsulated_packet = construct_packet(1, UDP_IP, port, socket.gethostbyname(
                    line[2]), int(line[3]), 'R'.encode(), 0, window_size, file_option.encode())

                sock.sendto(encapsulated_packet,
                            (host_name, emulator_port))  # for lab 2
                print("request sent")

                while True:
                    # buffer size is 1024 bytes
                    data, addr = sock.recvfrom(1024)
                    now = datetime.now()
                    # header = struct.unpack("!cII", data[:9])
                    header = struct.unpack(
                        "!BIHIHIcII", data[:26])  # for lab 2
                    print(f"packet {header[7]} received")


                    # skip if dest_ip is not own ip
                    decoded_ip = socket.inet_ntoa(struct.pack("!I", header[3]))
                    if decoded_ip != UDP_IP:
                        continue

                    packet_type = header[6].decode()
                    seq_no = header[7]
                    total_packets += 1
                    total_bytes += int(header[2])

                    packets_received.append((seq_no, data[26:]))

                    # stop sending ACKs; END packet received
                    if packet_type == 'E':  # modified for lab 2
                        # summary data
                        end = time.time()
                        run_time = end - start
                        avg_pckts_per_sec = total_packets / run_time
                        print('\nSummary')
                        print(f'sender addr:\t\t{socket.gethostbyname(line[2])}:{line[3]}\nTotal Data packets:\t{total_packets}\n' +
                              f'Total Data bytes:\t{total_bytes}\nAverage packets/second:\t{int(avg_pckts_per_sec)}\n' +
                              f'Duration of the test:\t{int(run_time * 1000)} ms')
                        break

                    ack_packet = construct_packet(1, UDP_IP, port, socket.gethostbyname(
                        line[2]), int(line[3]), 'A'.encode(), seq_no, window_size, b'')
                    sock.sendto(ack_packet, (host_name, emulator_port))
                    print(f"ACK {seq_no} sent")

        # convert list of all packets to sorted set and write to file
        for seq_no, payload in packets_received:
            if seq_no not in packet_dict:
                packet_dict[seq_no] = payload
        packets_sorted = sorted(packet_dict.items())
        print()
        print()
        for packet in packets_sorted:
            file.write(packet[1])

    except socket.timeout:
        print("timed out!")
    finally:
        file.close()
        sock.close()

# constructs a full packet for lab 2


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
