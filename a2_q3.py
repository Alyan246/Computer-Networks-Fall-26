import random

# conf and parameters
PROTOCOL = input("Enter a protocol (GBN or SR): ").strip().upper()
if PROTOCOL != "GBN" and PROTOCOL != "SR":
    print("No valid protocol detected, defaulting to GBN")
    PROTOCOL = "GBN"

NUM_PACKETS = 200        
WINDOW_SIZE_N = 4      
SEQ_BITS_K = 3         
MAX_SEQ = (2 ** SEQ_BITS_K)

# Channel Probabilities
LOSS_PROB = 0.0
CORRUPT_PROB = 0.0
DELAY_PROB = 0.0

scenario = input("Enter a scenario to run (A, B, or C): ").strip().upper()

if scenario == 'A':
    pass
elif scenario == 'B':
    LOSS_PROB = 0.1
elif scenario == 'C':
    LOSS_PROB = 0.05
    CORRUPT_PROB = 0.05
    DELAY_PROB = 0.1
else:
    print("No valid input detected, defaulting to scenario 'A'")

TIMEOUT_TICKS = 8
BASE_DELAY = 2           
EXTRA_DELAY = 5          

RANDOM_SEED = 743          # 743 as 0743 isn't allowed bcuz of leading zeros
random.seed(RANDOM_SEED)

# packet definition
class Packet:
    def __init__(self, seq_num, data, is_ack=False):
        self.seq_num = seq_num
        self.data = data
        self.is_ack = is_ack
        self.checksum = self._calculate_checksum()
        self.arrival_time = 0 

    def _calculate_checksum(self):
        return self.seq_num + hash(self.data)

    def corrupt(self):
        self.checksum += 1

    def is_corrupt(self):
        return self.checksum != self._calculate_checksum()

# unreliable channel
class UnreliableChannel:
    def __init__(self):
        self.in_transit = []

    def send(self, packet, current_tick, sender_name, receiver_name):
        if random.random() < LOSS_PROB:
            pkt_type = "ACK" if packet.is_ack else "Data Packet"
            print(f"[Tick {current_tick}] CHANNEL: {pkt_type} {packet.seq_num} from {sender_name} LOST in channel.")
            return

        if random.random() < CORRUPT_PROB:
            packet.corrupt()
            pkt_type = "ACK" if packet.is_ack else "Data Packet"
            print(f"[Tick {current_tick}] CHANNEL: {pkt_type} {packet.seq_num} from {sender_name} CORRUPTED.")

        delay = BASE_DELAY
        if random.random() < DELAY_PROB:
            delay += EXTRA_DELAY
            pkt_type = "ACK" if packet.is_ack else "Data Packet"
            print(f"[Tick {current_tick}] CHANNEL: {pkt_type} {packet.seq_num} from {sender_name} DELAYED.")

        packet.arrival_time = current_tick + delay
        self.in_transit.append((packet, receiver_name))
        
    def deliver(self, current_tick):
        arrived = []
        remaining = []
        for pkt, dest in self.in_transit:
            if pkt.arrival_time <= current_tick:
                arrived.append((pkt, dest))
            else:
                remaining.append((pkt, dest))
        self.in_transit = remaining
        return arrived

# GBN
class GBNSender:
    def __init__(self, channel, total_packets):
        self.channel = channel
        self.total_packets = total_packets
        self.base = 0
        self.nextseqnum = 0
        self.timer_start = -1
        self.buffer = [f"Payload_{i}" for i in range(total_packets)] 

    def tick(self, current_tick):
        if self.timer_start != -1 and (current_tick - self.timer_start >= TIMEOUT_TICKS):
            print(f"[Tick {current_tick}] GBN SENDER: Timeout for sequence {self.base % MAX_SEQ}! Resending outstanding packets.")
            self.timer_start = current_tick
            for i in range(self.base, self.nextseqnum):
                seq = i % MAX_SEQ
                print(f"[Tick {current_tick}] GBN SENDER: Retransmitting Data {seq}")
                pkt = Packet(seq, self.buffer[i])
                self.channel.send(pkt, current_tick, "Sender", "Receiver")

        while self.nextseqnum < self.base + WINDOW_SIZE_N and self.nextseqnum < self.total_packets:
            seq = self.nextseqnum % MAX_SEQ
            print(f"[Tick {current_tick}] GBN SENDER: Sending Data {seq}")
            pkt = Packet(seq, self.buffer[self.nextseqnum])
            self.channel.send(pkt, current_tick, "Sender", "Receiver")
            if self.base == self.nextseqnum:
                self.timer_start = current_tick
            self.nextseqnum += 1

    def receive_ack(self, packet, current_tick):
        if packet.is_corrupt():
            print(f"[Tick {current_tick}] GBN SENDER: Received corrupted ACK. Ignored.")
            return

        ack_num = packet.seq_num
        print(f"[Tick {current_tick}] GBN SENDER: Received cumulative ACK {ack_num}")

        unacked_count = self.nextseqnum - self.base
        for i in range(unacked_count):
            logical_seq = (self.base + i) % MAX_SEQ
            if logical_seq == ack_num:
                shift = i + 1
                self.base += shift
                if self.base == self.nextseqnum:
                    self.timer_start = -1
                else:
                    self.timer_start = current_tick
                return

class GBNReceiver:
    def __init__(self, channel):
        self.channel = channel
        self.expectedseqnum = 0

    def receive_packet(self, packet, current_tick):
        if packet.is_corrupt():
            print(f"[Tick {current_tick}] GBN RECEIVER: Received corrupted Data {packet.seq_num}. Discarding.")
            last_ack = (self.expectedseqnum - 1) % MAX_SEQ
            self._send_ack(last_ack, current_tick)
            return

        if packet.seq_num == self.expectedseqnum:
            print(f"[Tick {current_tick}] GBN RECEIVER: Received expected Data {packet.seq_num}. Delivering to application layer.")
            self._send_ack(self.expectedseqnum, current_tick)
            self.expectedseqnum = (self.expectedseqnum + 1) % MAX_SEQ
        else:
            print(f"[Tick {current_tick}] GBN RECEIVER: Out-of-order Data {packet.seq_num} (Expected {self.expectedseqnum}). Discarding.")
            last_ack = (self.expectedseqnum - 1) % MAX_SEQ
            self._send_ack(last_ack, current_tick)

    def _send_ack(self, ack_num, current_tick):
        print(f"[Tick {current_tick}] GBN RECEIVER: Sending cumulative ACK {ack_num}")
        ack_pkt = Packet(ack_num, "ACK", is_ack=True)
        self.channel.send(ack_pkt, current_tick, "Receiver", "Sender")



# SR

class SRSender:
    def __init__(self, channel, total_packets):
        self.channel = channel
        self.total_packets = total_packets
        self.base = 0
        self.nextseqnum = 0
        self.buffer = [f"Payload_{i}" for i in range(total_packets)]
        self.pkt_status = {} 
        self.pkt_timers = {}

    def tick(self, current_tick):
        for i in range(self.base, self.nextseqnum):
            if self.pkt_status.get(i) == 'sent':
                if current_tick - self.pkt_timers[i] >= TIMEOUT_TICKS:
                    seq = i % MAX_SEQ
                    print(f"[Tick {current_tick}] SR SENDER: Timeout for Data {seq}! Resending missing packet.")
                    self.pkt_timers[i] = current_tick
                    pkt = Packet(seq, self.buffer[i])
                    self.channel.send(pkt, current_tick, "Sender", "Receiver")

        while self.nextseqnum < self.base + WINDOW_SIZE_N and self.nextseqnum < self.total_packets:
            seq = self.nextseqnum % MAX_SEQ
            print(f"[Tick {current_tick}] SR SENDER: Sending Data {seq}")
            pkt = Packet(seq, self.buffer[self.nextseqnum])
            self.channel.send(pkt, current_tick, "Sender", "Receiver")
            self.pkt_status[self.nextseqnum] = 'sent'
            self.pkt_timers[self.nextseqnum] = current_tick
            self.nextseqnum += 1

    def receive_ack(self, packet, current_tick):
        if packet.is_corrupt():
            print(f"[Tick {current_tick}] SR SENDER: Received corrupted ACK. Ignored.")
            return

        ack_num = packet.seq_num
        print(f"[Tick {current_tick}] SR SENDER: Received individual ACK {ack_num}")
        
        for i in range(self.base, self.base + WINDOW_SIZE_N):
            if (i % MAX_SEQ) == ack_num and self.pkt_status.get(i) == 'sent':
                self.pkt_status[i] = 'acked'
                break

        while self.pkt_status.get(self.base) == 'acked':
            self.base += 1


class SRReceiver:
    def __init__(self, channel):
        self.channel = channel
        self.rcv_base = 0
        self.rcv_buffer = {}

    def receive_packet(self, packet, current_tick):
        if packet.is_corrupt():
            print(f"[Tick {current_tick}] SR RECEIVER: Received corrupted Data {packet.seq_num}. Discarding.")
            return

        seq = packet.seq_num
        print(f"[Tick {current_tick}] SR RECEIVER: Received Data {seq}")

        in_window = False
        logical_index = -1
        for i in range(self.rcv_base, self.rcv_base + WINDOW_SIZE_N):
            if (i % MAX_SEQ) == seq:
                in_window = True
                logical_index = i
                break

        in_prev_window = False
        for i in range(max(0, self.rcv_base - WINDOW_SIZE_N), self.rcv_base):
            if (i % MAX_SEQ) == seq:
                in_prev_window = True
                break

        if in_window:
            print(f"[Tick {current_tick}] SR RECEIVER: Sending individual ACK {seq}")
            ack_pkt = Packet(seq, "ACK", is_ack=True)
            self.channel.send(ack_pkt, current_tick, "Receiver", "Sender")
            
            if logical_index not in self.rcv_buffer:
                self.rcv_buffer[logical_index] = packet.data
                print(f"[Tick {current_tick}] SR RECEIVER: Buffered Data {seq}")
            while self.rcv_base in self.rcv_buffer:
                print(f"[Tick {current_tick}] SR RECEIVER: Delivering Data {self.rcv_base % MAX_SEQ} to application layer.")
                del self.rcv_buffer[self.rcv_base]
                self.rcv_base += 1

        elif in_prev_window:

            print(f"[Tick {current_tick}] SR RECEIVER: Duplicate Data {seq}. Resending individual ACK {seq}")
            ack_pkt = Packet(seq, "ACK", is_ack=True)
            self.channel.send(ack_pkt, current_tick, "Receiver", "Sender")
        else:
            print(f"[Tick {current_tick}] SR RECEIVER: Data {seq} outside bounds. Ignored.")

# MAIN LOOP
def run_simulation():
    print(f"Starting {PROTOCOL} Simulation")
    print(f"Packets: {NUM_PACKETS}, Window: {WINDOW_SIZE_N}, Max Seq: {MAX_SEQ-1}")
    
    channel = UnreliableChannel()
    
    if PROTOCOL == 'GBN':
        sender = GBNSender(channel, NUM_PACKETS)
        receiver = GBNReceiver(channel)
    else:
        sender = SRSender(channel, NUM_PACKETS)
        receiver = SRReceiver(channel)

    tick = 0
    
    while sender.base < NUM_PACKETS and tick < 5000: 
        arrived = channel.deliver(tick)
        for pkt, dest in arrived:
            if dest == "Receiver":
                receiver.receive_packet(pkt, tick)
            elif dest == "Sender":
                sender.receive_ack(pkt, tick)
                
        sender.tick(tick)
        
        tick += 1

    if sender.base == NUM_PACKETS:
        print(f"\nSimulation Complete in {tick} ticks")
        print("All packets successfully delivered.")
    else:
        print("\nSimulation Aborted (Safety threshold reached)")


run_simulation()