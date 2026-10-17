# GBN vs SR Reliable Data Transfer Simulator

A tick-based Python simulation of two sliding-window reliable transfer protocols over an unreliable channel:

- **GBN**: Go-Back-N (cumulative ACKs, receiver discards out-of-order packets, sender resends the whole outstanding window on timeout)
- **SR**: Selective Repeat (individual ACKs, receiver buffers out-of-order packets, sender resends only the packet that timed out)

The channel can lose, corrupt, and delay packets depending on the scenario you pick. The program logs every event, tick by tick, and reports how long it took to deliver everything.

## Requirements

- Python 3.6 or newer
- No external packages (only the standard library `random` module is used)

## How to run

```bash
python3 a2_q3.py
```

The program asks two questions:

```
Enter a protocol (GBN or SR): GBN
Enter a scenario to run (A, B, or C): B
```

## Expected inputs

| Prompt | Valid values | If invalid |
|---|---|---|
| Protocol | `GBN` or `SR` | Prints a message and defaults to `GBN` |
| Scenario | `A`, `B`, or `C` | Prints a message and defaults to `A` |

Input notes:

- Both inputs are **case-insensitive**. 
- Both inputs have surrounding whitespace trimmed.

## Scenarios

| Scenario | Loss | Corruption | Extra delay | Description |
|---|---|---|---|---|
| A | 0% | 0% | 0% | Perfect channel, no errors |
| B | 10% | 0% | 0% | Packet loss only |
| C | 5% | 5% | 10% | Mixed: loss, corruption, and delayed packets |

Each probability is applied independently to every packet sent, and it applies to both data packets and ACKs.

## Parameters

These are constants at the top of the file, as per the question in assignment.

| Parameter | Default | Meaning |
|---|---|---|
| `NUM_PACKETS` | `200` | Total number of data packets to deliver |
| `WINDOW_SIZE_N` | `4` | Sender window size (max unacknowledged packets in flight) |
| `SEQ_BITS_K` | `3` | Bits in the sequence number field |
| `MAX_SEQ` | `2 ** SEQ_BITS_K` = `8` | Sequence numbers wrap around: 0 to 7 |
| `TIMEOUT_TICKS` | `8` | Ticks the sender waits before retransmitting |
| `BASE_DELAY` | `2` | Normal one-way channel delay, in ticks |
| `EXTRA_DELAY` | `5` | Additional ticks added to a delayed packet (total delay 7) |
| `RANDOM_SEED` | `743` | Seed for the random number generator |

Channel probabilities (`LOSS_PROB`, `CORRUPT_PROB`, `DELAY_PROB`) are set by the scenario chosen.

Things to keep in mind when changing parameters:

- **GBN** requires `WINDOW_SIZE_N <= MAX_SEQ - 1`.
- **SR** requires `WINDOW_SIZE_N <= MAX_SEQ / 2`. The default of 4 with 3 sequence bits sits exactly at this limit. Going higher breaks SR, because the receiver can no longer tell a new packet from a retransmitted old one.
- `TIMEOUT_TICKS` should be larger than a full round trip (`2 * BASE_DELAY` = 4 ticks), otherwise you get unnecessary retransmissions even on a perfect channel.

## Reproducibility

The random generator is seeded with `RANDOM_SEED`, so running the same protocol and scenario twice gives identical output. Change the seed to see a different random sequence of losses, corruptions, and delays.

## What to expect as output

### 1. Header

```
Starting GBN Simulation
Packets: 200, Window: 4, Max Seq: 7
```

### 2. Event log

One line per event, prefixed with the tick number. Examples:

```
[Tick 0] GBN SENDER: Sending Data 0
[Tick 2] GBN RECEIVER: Received expected Data 0. Delivering to application layer.
[Tick 2] GBN RECEIVER: Sending cumulative ACK 0
[Tick 4] GBN SENDER: Received cumulative ACK 0
[Tick 5] CHANNEL: Data Packet 3 from Sender LOST in channel.
[Tick 13] GBN SENDER: Timeout for sequence 3! Resending outstanding packets.
```

Who prints what:

| Source | Events logged |
|---|---|
| `CHANNEL` | Packet or ACK **LOST**, **CORRUPTED**, or **DELAYED** |
| `SENDER` | Sending new data, receiving ACKs, timeouts, retransmissions, ignoring corrupted ACKs |
| `RECEIVER` | Receiving data, delivering to the application layer, discarding corrupted or out-of-order data, sending ACKs |

Differences between the protocols in the log:

- **GBN** logs *cumulative ACK* messages and `Out-of-order Data ... Discarding`. After a timeout it logs a `Retransmitting Data` line for every outstanding packet.
- **SR** logs *individual ACK* messages, `Buffered Data`, and `Duplicate Data ... Resending individual ACK`. After a timeout it resends only the one missing packet.

Sequence numbers in the log wrap around (0 to 7), so the same number appears many times over a 200-packet run.

### 3. Final result

On success:

```
Simulation Complete in 412 ticks
All packets successfully delivered.
```

The tick count is the main performance number. Lower means the protocol finished faster. Scenario A gives the baseline; B and C show how each protocol copes with errors.

If the run reaches 5000 ticks without finishing (a safety limit against infinite loops):

```
Simulation Aborted (Safety threshold reached)
```

## Tip: saving the log

The log is long (hundreds of lines), so redirect it to a file if you want to study it:

```bash
python3 simulation.py > output.txt
```

The prompts will not appear on screen when redirected, but they still read your typed input.

To run non-interactively, pipe the answers in:

```bash
printf "SR\nC\n" | python3 simulation.py > sr_scenario_c.txt
```

## How the code is organized

| Section | Purpose |
|---|---|
| Configuration | Constants, user prompts, scenario setup |
| `Packet` | Packet with sequence number, data, ACK flag, and checksum (corruption is simulated by altering the checksum) |
| `UnreliableChannel` | Holds packets in transit and applies loss, corruption, and delay |
| `GBNSender` / `GBNReceiver` | Go-Back-N logic |
| `SRSender` / `SRReceiver` | Selective Repeat logic |
| `run_simulation()` | Main loop: each tick, deliver arrived packets, then let the sender act |
