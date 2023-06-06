import argparse
import logging
import random
import socket
import struct
import time
import traceback


def main():  # can this be emulator or does it have to be main?
    parser = argparse.ArgumentParser(
        description="Process command line arguments")

    parser.add_argument('-p', required=True, help='port')
    parser.add_argument('-q', required=True, help='queue size')
    parser.add_argument('-f', required=True, help='filename')
    parser.add_argument('-l', required=True, help='log')

    args = parser.parse_args()
    port = int(args.p)
    queue_size = int(args.q)
    file_name = args.f
    log_file_name = args.l

    # emulator controls the routing, queuing, sending, and logging
    # END packets should never be dropped

    UDP_IP = socket.gethostbyname(socket.gethostname())

    q1 = list()
    q2 = list()
    q3 = list()

    # create log file
    log_file = open(log_file_name, "w")
    log_file.write("Lost packets:\n")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP, port))
    sock.setblocking(False)

    timeout_start = time.time()

    f_table_file = open(file_name, 'r')
    lines = f_table_file.readlines()

    delayed_packet = None
    delay_end_time = 0
    ex = False
    while True:
        # 1:  Receive packet in non-blocking way, if no packet received, jump to 4
        try:
            data, addr = sock.recvfrom(1024)
            # 2: Once packet is received, decide if packet should be forwarded using forwarding table
            header = struct.unpack("!BIHIHIcII", data[:26])
            print(f"received packet: {header} ")
            dest = header[3:5]
            dest_host = socket.gethostbyname(
                socket.inet_ntoa(struct.pack("!I", dest[0])))
            dest_port = dest[1]
            for line in lines:
                tokens = line.split()
                # skip line if not correct destination IP/Port
                if socket.gethostbyname(tokens[0]) != UDP_IP or tokens[1] != str(port):
                    print("skip line")
                    continue
                print(socket.gethostbyname(
                    tokens[2]), tokens[3], dest_host, dest_port)
                if socket.gethostbyname(tokens[2]) == dest_host and tokens[3] == str(dest_port):
                    # 3: Queue packet according to packet priority level if the queue is not full
                    packet_priority = header[0]
                    print(f"packet priority: {packet_priority}")
                    if packet_priority == 1 and len(q1) != queue_size:
                        q1.append((data, tokens))
                        print('prio 1 queued')
                    elif packet_priority == 2 and len(q2) != queue_size:
                        q2.append((data, tokens))
                        print('prio 2 queued')
                    elif packet_priority == 3 and len(q3) != queue_size:
                        q3.append((data, tokens))
                        print('prio 3 queued')

                    else:
                        # log dropped packet here : queue full
                        header = struct.unpack("!BIHIHIcII", data[:26])
                        log_file.write(log_to_file(
                            "QUEUE FULL", header[1], header[2], header[3], header[4], packet_priority, header[5]))
                        print('queue full')

                    break
            else:
                # log that no forwarding entry found
                header = struct.unpack("!BIHIHIcII", data[:26])
                log_file.write(log_to_file(
                    "NO FORWARDING ENTRY", header[1], header[2], header[3], header[4], packet_priority, header[5]))
        except socket.timeout:
            print("socket timedout")
            ex = True
        # except socket.timeout:
        except Exception as e:
            pass

         # 4: If a packet is currently being delayed and delay is not expired, go to step 1
        finally:
            # TODO set higher !!!
            if time.time() - timeout_start > 300:
                exit()

            if delayed_packet and time.time() < delay_end_time:
                # print("waiting for delayed packet")
                continue

            # all queues are empty
            if not any([q1, q2, q3]) and not delayed_packet:
                # print("queues empty")
                continue
            # 5: If no packet is being delayed, select packet at front of queue w/ highest prio, remove from queue and delay it
            if not delayed_packet:
                if q1:
                    delayed_packet = q1.pop(0)
                    delay_end_time = time.time() + int(delayed_packet[1][6])/1000
                elif q2:
                    delayed_packet = q2.pop(0)
                    delay_end_time = time.time() + int(delayed_packet[1][6])/1000
                elif q3:
                    delayed_packet = q3.pop(0)
                    delay_end_time = time.time() + int(delayed_packet[1][6])/1000

             # 6: When delay expires, randomly determine whether to drop the packet
            if time.time() > delay_end_time:
                # print("HERE")
                # drop packet
                header = struct.unpack("!BIHIHIcII", delayed_packet[0][:26])
                drop_prob = int(delayed_packet[1][7])
                if random.random()*100 <= drop_prob and header[6].decode() != "E":
                    # log dropped packet due to delay
                    log_file.write(log_to_file(
                        'PACKET RANDOMLY DROPPED DUE TO DELAY',  header[1], header[2], header[3], header[4], header[0], header[5]))
                # 7: Otherwise, send the packet to the next hop
                else:
                    sock.sendto(
                        delayed_packet[0], (delayed_packet[1][4], int(delayed_packet[1][5])))
                    print(f"packet sent to {delayed_packet[1][4:6]}")
                    print(f"packet # {header[6].decode()} {header[7]}")
                    print()
                delayed_packet = None
                delay_end_time = 0


def log_to_file(reason, src_host, src_port, dest_host, dest_port, priority, payload_size):
    src_host = socket.gethostbyaddr(
        socket.inet_ntoa(struct.pack("!I", src_host)))[0]
    dest_host = socket.gethostbyaddr(
        socket.inet_ntoa(struct.pack("!I", dest_host)))[0]
    return f'[{reason}] \nTime: {time.time()} \nSource Host: {src_host}, \nSource Port: {src_port}, \nDestination Host: {dest_host}, \nDestination Port: {dest_port}, \nPriority: {priority}, \nPayload Size: {payload_size}\n\n'


if __name__ == "__main__":
    main()
