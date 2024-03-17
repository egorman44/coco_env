# TODO: how to handle interface width:
# width < 8bit
# 8bit < width < 16bit ?


import random
import math
class Packet:

    dbg_words_in_line = 8
    dbg_fill = '0'
    dbg_width = 3
    
    # Class members:
    #   self.data
    #   self.delay
    
    def __init__(self, name, format_width=1, width=8):
        self.name         = name
        self.data         = []
        self.pkt_size     = None
        self.delay        = None
        self.format_width = format_width
        self.width        = width

    def copy(self, ref_pkt):
        self.data = ref_pkt.data.copy()
        self.pkt_size = len(ref_pkt.data)
        
    def compare(self, comp_pkt, verbose=0):
        if self.pkt_size != comp_pkt.pkt_size:
            print("[Warning] Packets length are not matched")
            return 1
        if self.data != comp_pkt.data:
            for indx in range(0,len(self.data)):
                if(self.data[indx] != comp_pkt.data[indx]):
                    print(f"[Warning] Words {self.name}[{indx}] != {comp_pkt.name}[{indx}] ")
                    print(f" \t {self.name}[{indx}] = 0x{self.data[indx]:{Packet.dbg_fill}{self.format_width}x}")
                    print(f" \t {comp_pkt.name}[{indx}] = 0x{comp_pkt.data[indx]:{Packet.dbg_fill}{self.format_width}x}")
            return 1
        print()
        if(verbose):
            print(f"[Info] Packets {self.name} {comp_pkt.name} are equal")
        
    def check_pkt(self):
        if len(self.data) == 0:
            assert False, "[ERROR] Packet is not generated."

    #---------------------------------
    # Generate based on ref_pkt.
    #---------------------------------
    def generate_ref_pkt(self, ref_pkt, delay = None, delay_type = 'short'):
        self.gen_delay(delay, delay_type)
        self.copy(ref_pkt)
        
    #---------------------------------
    # Generate method.
    #---------------------------------

    def generate(self, pkt_size = None, pkt_size_type = 'random', pattern = 'random', delay = None, delay_type = 'short'):
        # Generate packet and delay members.
        self.gen_pkt_size(pkt_size, pkt_size_type)        
        self.gen_delay(delay, delay_type)
        self.gen_data(pattern)
        
    #---------------------------------
    # Generate pkt_size.
    #---------------------------------
    
    def gen_pkt_size(self, pkt_size, pkt_size_type):
        # If pkt_size was not set
        if pkt_size is not None:
            self.pkt_size = pkt_size
        else:
            if pkt_size_type == 'random':
                pkt_size_type = random.choice(['small', 'medium', 'long'])
                # Randomize pkt_size
            if pkt_size_type == 'one_word':
                self.pkt_size = random.randint(1,10)            
            elif pkt_size_type == 'small':
                self.pkt_size = random.randint(10,100)
            elif pkt_size_type == 'medium':
                self.pkt_size = random.randint(100, 500)
            elif pkt_size_type == 'long':
                self.pkt_size = random.randint(500, 1500)
            else:
                raise ValueError("[ERROR] Invalid pkt_size_type: " + str(pkt_size_type))
    
    #---------------------------------
    # Generate delay
    #---------------------------------
    def gen_delay(self, delay_type, delay=None):
        if delay is not None:
            self.delay = delay
        else:
            if delay_type == 'no_delay':
                self.delay = 0
            elif delay_type == 'short':
                self.delay = random.randint(1,5)
            elif delay_type == 'medium':
                self.delay = random.randint(5,50)
            elif delay_type == 'long':
                self.delay = random.randint(50,250)
            else:
                self.delay = random.randint(500, 1000)        

    #---------------------------------
    # Generate data
    #---------------------------------
    def gen_data(self, pattern, ref_pkt = None):        
        # Calculates words number and valid bytes in the last cycle of the transaction
        pkt_size_in_words = math.ceil(self.pkt_size / self.format_width)
        last_word_bytes_valid = self.pkt_size % self.format_width
        if(pattern == 'increment'):
            for word_indx in range(pkt_size_in_words):
                word = word_indx % 8*self.format_width
                self.data.append(word)
        else:
            print("[WARNING] :none of the known patterns are used. \'random\' is choosen.")
            for indx in range(self.pkt_size):
                self.data.append(random.randint(0, 2**self.width-1))
                    
    #---------------------------------
    # Convert data into the byte list
    #---------------------------------
    
    def get_word_list(self, word_size):
        word_list = []
        word = 0        
        for i in range(self.pkt_size):
            word = word | (self.data[i] << (i % word_size)*8)
            if (i % word_size == word_size-1) or (i == len(self.data)-1):                
                word_list.append(word)
                word = 0
        return word_list

    def write_word_list(self, word_list, pkt_size, word_size, msb_first=1):
        self.data = []
        word_cntr = 0
        byte_cntr = 0
        self.pkt_size = pkt_size
        for i in range(pkt_size):
            byte_cntr = i % word_size
            #if(msb_first):
            #    byte = (word_list[word_cntr] >> ((word_size-1-byte_cntr) * 8)) & 0xFF                
            #else:
            #    byte = (word_list[word_cntr] >> (byte_cntr * 8)) & 0xFF
            byte = (word_list[word_cntr] >> (byte_cntr * 8)) & 0xFF
            #print(f"word_list[word_cntr] = {word_list[word_cntr]:x} byte = {byte}")
            self.data.append(byte)
            if(byte_cntr) == word_size - 1:
                word_cntr += 1
                
    def write_number(self, val, width_in_bits):
        byte_list = []
        self.data = []
        self.pkt_size = math.ceil(width_in_bits/8)
        for i in range(self.pkt_size):
            self.data.append((val >> i*8) & 0xFF)

    #---------------------------------
    # Corrupt data list
    #---------------------------------

    def corrupt_pkt(self, corrupts):
        if isinstance(corrupts, list):
            corrupt_words = corrupts        
        else:
            corrupt_words = random.sample(range(0,len(self.data)), corrupts)
        for word in corrupt_words:
            bit_position = random.randint(0, 7)
            self.data[word] = self.data[word] ^ (1 << bit_position)        
                
    #---------------------------------
    # Print packet
    #---------------------------------
    def print_pkt(self, source = ''):
        word_indx = 0
        dbg = ''
        if source:            
            dbg = source + '\n'
        dbg = dbg + f"\t PKT_NAME    : {self.name} \n"
        dbg = dbg + f"\t FORMAT_WIDTH: {self.format_width}\n"
        dbg = dbg + f"\t PKT_SIZE    : {self.pkt_size}\n"
        if self.delay is not None:
            dbg = dbg + f"\t DELAY       : {self.delay}\n"
        dbg = dbg + f"\t DATA        : \n"
        for word_indx in range (len(self.data)):
            if word_indx % Packet.dbg_words_in_line == 0:
                dbg = dbg + "\n"
                dbg = dbg + f"\t\t{word_indx:{Packet.dbg_fill}{Packet.dbg_width}d}: "
            #dbg = dbg + f" 0x{self.data[word_indx]:{Packet.dbg_fill}{self.format_width}x} "
            dbg = dbg + f" 0x{self.data[word_indx]:02x} "
            word_indx += 1

        dbg = dbg + "\n"
        print(dbg)
