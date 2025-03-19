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
    
    def __init__(self, name, format_width=1, width=8, symb_width=8):
        self.name         = name
        self.data         = []
        self.user         = []
        self.pkt_size     = None
        self.delay        = None
        self.format_width = format_width
        self.width        = width
        self.symb_width   = symb_width
        
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
        if(verbose):
            print(f"[Info] Packets {self.name} {comp_pkt.name} are equal")
        
    #---------------------------------
    # Generate user data.
    #---------------------------------
    def gen_user(self, user):
        self.user = user.copy()

    #---------------------------------
    # Generate based on ref_pkt.
    #---------------------------------
    def write_data(self, ref_data, delay = None, delay_type = 'short'):
        self.data = ref_data.copy()
        self.pkt_size = len(ref_data)
        self.gen_delay(delay)        
        
    #---------------------------------
    # Generate method.
    #---------------------------------

    def generate(self, pkt_size: int=None, delay: int=None, pattern: str='random'):
        # Generate packet and delay members.
        self.gen_pkt_size(pkt_size)        
        self.gen_delay(delay)
        self.gen_data(pattern)
    
    #---------------------------------
    # Generate pkt_size.
    #---------------------------------

    
    def gen_pkt_size(self, pkt_size):
        if pkt_size is None:
            self.pkt_size = random.randint(1, 1500)
        elif isinstance(pkt_size, int):
            if pkt_size <= 0:
                raise ValueError("[ERROR] Packet size must be a positive integer.")
            self.pkt_size = pkt_size
        elif isinstance(pkt_size, str):
            if pkt_size.isdigit():
                self.pkt_size = int(pkt_size)
            else:
                # Packet size ranges mapping (keys in lowercase)
                pkt_size_ranges = {
                    'random': (1, 1500),
                    'one_word': (1, 10),
                    'small': (10, 100),
                    'medium': (100, 500),
                    'long': (500, 1500)
                }

            # Fetch range safely and generate packet size
            pkt_range = pkt_size_ranges.get(pkt_size.lower())
            if pkt_range:
                self.pkt_size = random.randint(*pkt_range)
            else:
                raise ValueError(f"[ERROR] Invalid pkt_size: {pkt_size}")
        else:
            raise TypeError("[ERROR] Expected an integer or a valid string for pkt_size.")
        
    #---------------------------------
    # Generate delay
    #---------------------------------
    
    def gen_delay(self, delay):
        if delay is None:
            self.delay = random.randint(0, 250)
        elif isinstance(delay, int):
            if delay < 0:
                raise ValueError("[ERROR] Delay must be a non-negative integer.")
            self.delay = delay
        elif isinstance(delay, str):
            if delay.isdigit():
                self.delay = int(delay)
            else:
                # Delay ranges mapping (keys in lowercase)
                delay_ranges = {
                    'random': (0, 250),
                    'no_delay': (0, 0),
                    'short': (0, 5),
                    'medium': (5, 50),
                    'long': (50, 250)
                }
    
                # Fetch range safely and generate delay
                delay_range = delay_ranges.get(delay.lower())
                if delay_range:
                    self.delay = random.randint(*delay_range)
                else:
                    raise ValueError(f"[ERROR] Invalid delay value: {delay}")
        else:
            raise TypeError("[ERROR] Expected an integer or a valid string for delay.")
            
    #---------------------------------
    # Generate data
    #---------------------------------
    def gen_data(self, pattern):        
        # Calculates words number and valid bytes in the last cycle of the transaction
        pkt_size_in_words = math.ceil(self.pkt_size / self.format_width)
        last_word_bytes_valid = self.pkt_size % self.format_width
        if(pattern == 'increment'):
            for indx in range(self.pkt_size):
                self.data.append(indx % (2**self.width-1))
        else:
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

    def write_word_list(self, word_list, pkt_size, word_size):
        self.data = []
        word_cntr = 0
        byte_cntr = 0
        self.pkt_size = pkt_size
        for i in range(pkt_size):
            byte_cntr = i % word_size
            byte = (word_list[word_cntr] >> (byte_cntr * 8)) & 0xFF
            self.data.append(byte)
            if(byte_cntr) == word_size - 1:
                word_cntr += 1
                
    def write_number(self, val, width_in_bits):
        byte_list = []
        self.data = []
        self.pkt_size = math.ceil(width_in_bits/8)
        for i in range(self.pkt_size):
            self.data.append((val >> i*8) & 0xFF)

    '''
    corrupt_pkt - method to corrupt the packet. 
    If position is int then it defines the number of symbols that needs to 
    be corrupted. If it's list then positions itself are provided. 
    '''
    
    def corrupt_pkt(self, err_pos, err_val=None, pattern='random'):
        if isinstance(err_pos, list):
            pass
        elif isinstance(err_pos, int):
            err_pos = random.sample(range(0,len(self.data)), err_pos)
        else:
            raise TypeError(f"Expected integer or list datatypes, but got {type(variable).__name__}")        
        print(f"[INFO] Corrupt symbols in err_pos: {err_pos}")
        err_list = []
        for i in range(len(err_pos)):
            if err_val is not None:
                error = err_val[i]
            else:
                if pattern == 'random':                    
                    error = random.randint(1, 2** self.symb_width-1)
                elif pattern == 'bit_error':
                    bit_position = random.randint(0, 7)
                    error = 1 << bit_position
                else:
                    raise ValueError(f"Not expected value for pattern = {pattern}.")
            err_list.append(error)
            self.data[err_pos[i]] = self.data[err_pos[i]] ^ error
        print(f"error = {err_list}")

                            
    #---------------------------------
    # Print packet
    #---------------------------------
    def print_pkt(self, source = ''):
        word_indx = 0
        dbg = ''
        if source:            
            dbg = source + '\n'
        dbg = dbg + f"\n\t PKT_NAME    : {self.name} \n"
        dbg = dbg + f"\t FORMAT_WIDTH: {self.format_width}\n"
        dbg = dbg + f"\t PKT_SIZE    : {self.pkt_size}\n"
        if self.delay is not None:
            dbg = dbg + f"\t DELAY       : {self.delay}\n"
        if self.user:
            dbg = dbg + f"\t USER        : {self.user[0]}\n"
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
