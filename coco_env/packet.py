from typing import List

class Packet:
    def __init__(self, name):
        self.name = name
        self.data = []
        self.user = []
        self.pkt_size = 0
        self.delay = 0
        self.bytes_in_line = 8

    def print_packet(self):
        """Prints the packet data in a hex dump format."""
        if not self.data:
            print(f"Packet {self.name} is empty")
            return

        max_pos = max(0, len(self.data) - 1)
        pos_width = len(str(max_pos))

        for i in range(0, len(self.data), self.bytes_in_line):
            chunk = self.data[i : i + self.bytes_in_line]
            hex_bytes = " ".join(f"{b:02x}" for b in chunk)
            print(f"{i:0{pos_width}d}: {hex_bytes}")

    def words_to_bytes(self, word_list: List[int], total_bytes: int, width: int) -> None:
        """Converts a list of multi-byte words into a list of bytes.

        Args:
            word_list: List of integers representing words correctly packed
            total_bytes: Total number of valid bytes in the packet
            width: Width of the interface in bytes
        """
        self.pkt_size = total_bytes
        byte_list = []

        for word in word_list:
            for i in range(width):
                if len(byte_list) < total_bytes:
                    byte_list.append((word >> (i * 8)) & 0xFF)
                else:
                    break
        self.data = byte_list
