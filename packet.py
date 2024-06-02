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
        print()
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
        self.gen_delay(delay_type, delay)        
        
    #---------------------------------
    # Generate method.
    #---------------------------------

    def generate(self, pkt_size = None, pkt_size_type = 'random', pattern = 'random', delay = None, delay_type = 'short'):
        # Generate packet and delay members.
        self.gen_pkt_size(pkt_size, pkt_size_type)        
        self.gen_delay(delay_type, delay)
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
    
    def corrupt_pkt(self, positions, errors=None, pattern='random'):
        if isinstance(positions, list):
            pass
        elif isinstance(positions, int):
            positions = random.sample(range(0,len(self.data)), positions)
        else:
            raise TypeError(f"Expected integer or list datatypes, but got {type(variable).__name__}")
        print(f"[INFO] Corrupt symbols in positions: {positions}")
        err_list = []
        for i in range(len(positions)):
            if errors is not None:
                error = errors[i]
            else:
                if pattern == 'random':                    
                    error = random.randint(1, 2** self.symb_width-1)
                elif pattern == 'bit_error':
                    bit_position = random.randint(0, 7)
                    error = 1 << bit_position
                else:
                    raise ValueError(f"Not expected value for pattern = {pattern}.")
            err_list.append(error)
            self.data[positions[i]] = self.data[positions[i]] ^ error
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
