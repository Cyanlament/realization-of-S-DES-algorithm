// Independent, string-based S-DES reference. No Python code/tables are imported.
// Compile: g++ -std=c++11 -O2 reference/sdes_reference.cpp -o build/sdes_reference
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

using std::string;

string select_bits(const string& input, const std::vector<int>& indices) {
    string result;
    for (int index : indices) result += input.at(index - 1);
    return result;
}

string bits(int value, int count) {
    string result(count, '0');
    for (int position = count - 1; position >= 0; --position) {
        result[position] = '0' + (value % 2);
        value /= 2;
    }
    return result;
}

string shift_half(const string& half, int count) {
    return half.substr(count) + half.substr(0, count);
}

std::vector<string> key_schedule(const string& key) {
    string permuted = select_bits(key, {3,5,2,7,4,10,1,9,8,6});
    string left = shift_half(permuted.substr(0,5), 1);
    string right = shift_half(permuted.substr(5,5), 1);
    string first = select_bits(left + right, {6,3,7,4,8,5,10,9});
    left = shift_half(left, 2);
    right = shift_half(right, 2);
    return {first, select_bits(left + right, {6,3,7,4,8,5,10,9})};
}

string xor_bits(const string& first, const string& second) {
    string result;
    for (unsigned i = 0; i < first.size(); ++i)
        result += first[i] == second[i] ? '0' : '1';
    return result;
}

string box_lookup(const string& input, const int box[4][4]) {
    int row = 2 * (input[0] - '0') + (input[3] - '0');
    int column = 2 * (input[1] - '0') + (input[2] - '0');
    return bits(box[row][column], 2);
}

string feistel(const string& block, const string& subkey) {
    const int box_one[4][4] = {{1,0,3,2},{3,2,1,0},{0,2,1,3},{3,1,0,2}};
    const int box_two[4][4] = {{0,1,2,3},{2,3,1,0},{3,0,1,2},{2,1,0,3}};
    string right = block.substr(4,4);
    string mixed = xor_bits(select_bits(right, {4,1,2,3,2,3,4,1}), subkey);
    string boxes = box_lookup(mixed.substr(0,4), box_one) + box_lookup(mixed.substr(4,4), box_two);
    return xor_bits(block.substr(0,4), select_bits(boxes, {2,4,3,1})) + right;
}

string transform(const string& block, const std::vector<string>& keys, bool decrypt) {
    string state = select_bits(block, {2,6,3,1,4,8,5,7});
    state = feistel(state, keys[decrypt ? 1 : 0]);
    state = state.substr(4,4) + state.substr(0,4);
    state = feistel(state, keys[decrypt ? 0 : 1]);
    return select_bits(state, {4,1,3,5,7,2,8,6});
}

void require_bits(const string& value, unsigned size) {
    if (value.size() != size || value.find_first_not_of("01") != string::npos)
        throw std::invalid_argument("Invalid binary input width or character");
}

int main(int argc, char** argv) {
    try {
        if (argc == 3 && string(argv[1]) == "--table") {
            std::ofstream output(argv[2], std::ios::binary);
            if (!output) throw std::runtime_error("Cannot open output file");
            for (int key = 0; key < 1024; ++key) {
                auto keys = key_schedule(bits(key, 10));
                for (int plaintext = 0; plaintext < 256; ++plaintext) {
                    int cipher = std::stoi(transform(bits(plaintext, 8), keys, false), nullptr, 2);
                    output.put(static_cast<char>(cipher));
                }
            }
            if (!output) throw std::runtime_error("Failed to write output");
        } else if (argc == 4 && (string(argv[1]) == "encrypt" || string(argv[1]) == "decrypt")) {
            require_bits(argv[2], 8);
            require_bits(argv[3], 10);
            std::cout << transform(argv[2], key_schedule(argv[3]), string(argv[1]) == "decrypt") << '\n';
        } else {
            std::cerr << "Usage: sdes_reference --table output.bin | encrypt/decrypt BLOCK KEY\n";
            return 2;
        }
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 2;
    }
    return 0;
}
