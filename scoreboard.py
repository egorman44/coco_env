#----------------------------------------------
# Packet comparator.
#----------------------------------------------

class Comparator:

    def __init__(self, name):
        self.name = name
        self.port_prd = []
        self.port_out = []

    def compare_out_of_order(self):
        prd_hash_tbl = {}
        for pkt in self.port_prd:
            prd_hash = f'{hash(tuple(pkt.data))}'
            prd_hash_tbl[prd_hash] = pkt
        for pkt in self.port_out:
            out_hash = f'{hash(tuple(pkt.data))}'
            if out_hash not in prd_hash_tbl:
                assert False , f"[TEST_FALIED] There is no predicted packet for {pkt.name()}"
            else:
                if pkt.compare(prd_hash_tbl[out_hash],1):
                    pkt.print_pkt()
                    prd_hash_tbl[out_hash].print_pkt()
                    assert False , f"[TEST_FALIED] Packets are not equal"            
        print(f"\n[{self.name}] Packets are equal. Congradulations!\n")
        
    def compare(self):
        print(f"\n[{self.name}] {self.name} STATISTIC:")
        print(f"\t Num of prd tnx: {len(self.port_prd)}")
        for pkt in self.port_prd:
            print(f"\t{pkt.name} : {len(pkt.data)}")
        print(f"\t Num of out tnx: {len(self.port_out)}")
        for pkt in self.port_out:
            print(f"\t{pkt.name} : {len(pkt.data)}")
        if len(self.port_prd) != len(self.port_out):
            assert False , f"[TEST_FALIED] Number of transactions are not equal. \n\t len(port_prd) = {len(self.port_prd)} \n\t len(port_out) = {len(self.port_out)}"
        for indx in range (0,len(self.port_prd)):
            if(self.port_out[indx].compare(self.port_prd[indx],1)):
                self.port_out[indx].print_pkt()
                self.port_prd[indx].print_pkt()
                assert False , f"[TEST_FALIED] Packets are not equal"            
        print(f"\n[{self.name}] Packets are equal. Congradulations!\n")

    def print_statistic(self):
        for pkt in self.port_prd:
            print(f"[{self.name}] PREDICTED PACKETS")

class Predictor:

    def __init__(self, name, port_prd):
        self.name = name
        self.port_in = []
        self.port_prd = port_prd
        
    def predict(self):
        '''Override the method to convert one type of packet 
        to another'''
        for pkt in self.port_in:
            self.port_prd.append(pkt)
        
