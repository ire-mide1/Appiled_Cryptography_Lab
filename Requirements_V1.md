Overview: The project will build a simple file encryption and decryption tool. The user picks a file, chooses whether to encrypt or decrypt it, and saves the result to a new file. Each byte of the input is first scrambled with a fixed bit permutation and then ⨁ with a byte produced by a 19-bit Linear Feedback Shift Register (LFSR). Decryption does the same steps in reverse:  ⨁ with the same LFSR stream, then apply the inverse permutation, which gives back the original file. The initial key is 0x67BD5, the LFSR polynomial (p(x) = 1 + x¹⁴ + x¹⁷ + x¹⁸ + x¹⁹), and it is 8-bit permutation. Bit ordering is defined strictly so that files encrypted through one implementation can be decrypted by another.

Project Requirements

1. The code will be written in Python.
2. The user interface will use Tkinter.
3. The user interface will let the user choose between “Encrypt” and “Decrypt”.0
4. The user interface will let the user select an input file.
5. The user interface will let the user specify an output file.
6. The UI will have a button called “Start” which begins the operation.
7. When encrypting, every byte will be permuted first and then ⨁ with one byte of LFSR output. When decrypting, every byte will be ⨁ with the same LFSR byte first and then passed through the inverse permutation.
8. The program will use these values: a 19-bit initial key of 0x67BD5, the LFSR polynomial p(x) = 1 + x¹⁴ + x¹⁷ + x¹⁸ + x¹⁹ (taps at positions 14, 17, 18 and 19), and the byte permutation π(1) = 2, π(2) = 6, π(3) = 3, π(4) = 5, π(5) = 1, π(6) = 8, π(7) = 4, π(8) = 7.
9. The leftmost bit of the LFSR will correspond to “x” in the polynomial and will be treated as the LSB. The “1” in the polynomial applies to the feedback bit.
10. The feedback bit will be shifted into the register from the left side.
11. The LSB of the seed will be loaded into the LSB position of the LFSR, so the first bit shifted out is the MSB of the seed.
12. When eight output bits are assembled into a keystream byte, the first bit output becomes the LSB of that byte.
13. When applying the permutation, index “1” refers to the most significant bit of the byte.
14. The UI will show a progress bar that updates while the file is being processed.
15. The program will work on any file type, including text, images and binaries, and the output file will be exactly the same size as the input.