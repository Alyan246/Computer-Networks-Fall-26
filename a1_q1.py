import socket
import struct
import random

def encode_dns_name(domain: str) -> bytes:
    parts = domain.strip('.').split('.')
    encoded = b''
    for part in parts:
        if not part:
            continue
        encoded += bytes([len(part)]) + part.encode('utf-8')
    encoded += b'\x00'
    return encoded


def decode_dns_name(data: bytes, offset: int) -> tuple[str, int]:
    labels = []
    jumped = False
    next_offset = offset

    while True:
        if offset >= len(data):
            break
        length = data[offset]
        if length == 0:
            if not jumped:
                next_offset = offset + 1
            break
        if (length & 0xC0) == 0xC0:
            if not jumped:
                next_offset = offset + 2
            pointer_offset = ((length & 0x3F) << 8) | data[offset + 1]
            offset = pointer_offset
            jumped = True
        else:
            offset += 1
            labels.append(data[offset:offset + length].decode('utf-8', errors='ignore'))
            offset += length
            if not jumped:
                next_offset = offset

    return ".".join(labels), next_offset


def build_dns_query(domain: str, tx_id: int) -> bytes:
    flags = 0x0100
    qdcount = 1
    ancount = 0
    nscount = 0
    arcount = 0

    header = struct.pack("!HHHHHH", tx_id, flags, qdcount, ancount, nscount, arcount)

    qname = encode_dns_name(domain)
    question = qname + struct.pack("!HH", 1, 1)

    return header + question


def parse_dns_response(data: bytes, expected_tx_id: int):
    if len(data) < 12:
        print("Error: Received response is too short to be a valid DNS message")
        return

    tx_id, flags, qdcount, ancount, nscount, arcount = struct.unpack("!HHHHHH", data[:12])

    rcode = flags & 0x000F
    qr = (flags >> 15) & 0x1
    rd = (flags >> 8) & 0x1
    ra = (flags >> 7) & 0x1

    rcode_map = {
        0: "NOERROR (Success)",
        1: "FORMERR (Format Error)",
        2: "SERVFAIL (Server Failure)",
        3: "NXDOMAIN (Non-Existent Domain)",
        4: "NOTIMP (Not Implemented)",
        5: "REFUSED (Query Refused)"
    }
    status_str = rcode_map.get(rcode, f"UNKNOWN ({rcode})")

    print("\n")
    print("DNS HEADER INFO")
    print(f"Transaction ID: {hex(tx_id)} (Expected: {hex(expected_tx_id)})")
    print(f"Response Status: {status_str}")
    print(f"Header Flags: Response Bit={qr} | RD={rd} | RA={ra}")
    print(f"Record Counts: Questions={qdcount} | Answers={ancount} | Authority={nscount} | Additional={arcount}")

    if tx_id != expected_tx_id:
        print("Warning: Transaction ID mismatch")

    if rcode != 0:
        print(f"\nQuery unfulfilled by server: {status_str}")
        return

    offset = 12

    for _ in range(qdcount):
        _, offset = decode_dns_name(data, offset)
        offset += 4

    print("\n")
    print(f"ANSWER SECTION ({ancount} Records)")

    if ancount == 0:
        print("No A records returned")
        return

    for i in range(ancount):
        aname, offset = decode_dns_name(data, offset)
        atype, aclass, ttl, rdlength = struct.unpack("!HHIH", data[offset:offset+10])
        offset += 10
        rdata = data[offset:offset+rdlength]
        offset += rdlength

        if atype == 1 and rdlength == 4:
            ip_address = socket.inet_ntoa(rdata)
            print(f" [{i+1}] Name   : {aname}")
            print(f"Type: A (IPv4)")
            print(f"TTL: {ttl} seconds")
            print(f"IP: {ip_address}\n")
        elif atype == 5:
            cname, _ = decode_dns_name(data, offset - rdlength)
            print(f" [{i+1}] Name   : {aname}")
            print(f"Type: CNAME (Alias)")
            print(f"TTL: {ttl} seconds")
            print(f"Target: {cname}\n")
        else:
            print(f"[{i+1}] Name: {aname}")
            print(f"Type: {atype}")
            print(f"TTL: {ttl} seconds")
            print(f"Length: {rdlength} bytes\n")


def main():
    print("Custom Low-Level DNS Query Tool")
    server_ip = input("Enter DNS Server IP (default: 8.8.8.8): ").strip()
    if not server_ip:
        server_ip = "8.8.8.8"

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(4.0)

    while True:
        try:
            print("\n" + "-"*50)
            domain = input("Enter domain name (or 'exit' to quit): ").strip()
            
            if domain.lower() in ('exit', 'quit', ''):
                print("Exiting application...")
                break

            if " " in domain or not all(c.isalnum() or c in ".-" for c in domain):
                print("Invalid domain format. Please enter a valid hostname.")
                continue

            tx_id = random.randint(0, 65535)
            query_packet = build_dns_query(domain, tx_id)

            print(f"Sending DNS query for '{domain}' to {server_ip}:53...")
            sock.sendto(query_packet, (server_ip, 53))

            response_data, _ = sock.recvfrom(1024)
            parse_dns_response(response_data, tx_id)

        except socket.timeout:
            print(f"Error: Request timed out. No response from DNS server ({server_ip}).")
        except socket.gaierror:
            print(f"Error: Provided DNS Server IP '{server_ip}' is invalid.")
            break
        except Exception as e:
            print(f"An unexpected error occurred: {e}")

    sock.close()


main()