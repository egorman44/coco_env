def countones(n):
    count = 0
    while (n):
        count += n & 1
        n = n >> 1
    return count

def check_pos(in_vect, pos):
    if((in_vect >> pos) & 1):
        return True
    else:
        return False

def get_byte_list(word_list, word_width, bytes_num):
    byte_list = []
    word_indx = 0
    for byte_indx in range (bytes_num):
        byte_list.append((word_list[word_indx] >> (byte_indx % word_width)*8) & 0xFF)
        if (byte_indx % word_width) == word_width-1:
            word_indx += 1
    return byte_list            

def get_word_list(byte_list, word_width, bytes_num):
    word_list = []
    word_indx = 0
    word      = 0
    for byte_indx in range (bytes_num):
        word = (byte_list[byte_indx] << (byte_indx % word_width)*8) | word
        if (byte_indx % word_width) == word_width-1 or byte_indx == bytes_num-1:
            word_list.append(word)
            word = 0
    return word_list

            
