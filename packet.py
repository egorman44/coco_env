import random
import math
class Packet:

    dbg_words_in_line = 8
    dbg_fill = '0'
    dbg_width = 3
    
    # Class members:
    #   self.data
    #   self.word_size
    #   self.delay
    
    def __init__(self, word_size = 1):
        self.word_size    = word_size
        self.data         = []
        self.pkt_size     = None
        self.delay        = None
        self.format_width = int(self.word_size)*2

    def compare(self, comp_pkt):
        if len(self.data) != len(comp_pkt.data):
            print("[Warning] Packets length are not matched")
            return 1
        if self.data != comp_pkt.data:
            for indx in range(0,len(self.data)):
                if(self.data[indx] != comp_pkt.data[indx]):
                    print(f"[Warning] Words pkt0[{indx}] != pkt1[{indx}] ")
                    print(f" \t pkt0[{indx}] = 0x{self.data[indx]:{Packet.dbg_fill}{self.format_width}x}")
                    print(f" \t pkt1[{indx}] = 0x{comp_pkt.data[indx]:{Packet.dbg_fill}{self.format_width}x}")
                    break
            return 1
                    
    def check_pkt(self):
        if len(self.data) == 0:
            assert False, "[ERROR] Packet is not generated."
            
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
                self.pkt_size = random.randint(1,self.word_size)            
            elif pkt_size_type == 'small':
                self.pkt_size = random.randint(self.word_size+1, self.word_size*5)
            elif pkt_size_type == 'medium':
                self.pkt_size = random.randint(self.word_size*5, self.word_size*50)
            elif pkt_size_type == 'long':
                self.pkt_size = random.randint(self.word_size*50, self.word_size*150)
            else:
                raise ValueError("[ERROR] Invalid pkt_size_type: " + str(pkt_size_type))
        print(f"gen_pkt_size : {self.pkt_size}")
            
            
    #---------------------------------
    # Generate delay
    #---------------------------------
    def gen_delay(self, delay, delay_type):
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
        # Generate data using pattern
        pkt_size_in_words = math.ceil(self.pkt_size / self.word_size)
        print(f"pkt_size_in_words = {pkt_size_in_words}")
        if(pattern == 'increment'):
            for word_indx in range(pkt_size_in_words):
                word = word_indx % 8*self.word_size
                self.data.append(word)
        else:
            print("[WARNING] :none of the known patterns are used. \'random\' is choosen.")
            for word_indx in range(pkt_size_in_words):
                word = random.randint(0, 2**(8*self.word_size))
                self.data.append(word)

    #---------------------------------
    # Print packet
    #---------------------------------
    def print_pkt(self, source = ''):
        word_indx = 0
        dbg = ''
        if source:            
            dbg = dbg + source + '\n'
        dbg = dbg + f"\t WORD_SIZE: {self.word_size}\n"
        dbg = dbg + f"\t PKT_SIZE : {self.pkt_size}\n"
        dbg = dbg + f"\t DATA     : \n"
        for word_indx in range (len(self.data)):
            if word_indx % Packet.dbg_words_in_line == 0:
                dbg = dbg + "\n"
                dbg = dbg + f"\t\t0x{word_indx:{Packet.dbg_fill}{Packet.dbg_width}x}: "
            dbg = dbg + f" 0x{self.data[word_indx]:{Packet.dbg_fill}{self.format_width}x} "
            word_indx += 1

        dbg = dbg + "\n"
        print(dbg)
