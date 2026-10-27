How the LFSR and the permutation work (Design v1)
=================================================

This explains Sections 2.2 and 2.3 of [Design_v1.md](Design_v1.md) in detail, with the first two keystream bytes worked out clock by clock from the seed `0x67BD5`.

1. The LFSR
-----------

**1.1 What the register is**

A 19-bit shift register. Its contents are the **state**, a 19-bit number. The polynomial p(x) = 1 + x¹⁴ + x¹⁷ + x¹⁸ + x¹⁹ decides which bits are combined to make the new bit.

| Register bit | Polynomial term | Role |
|---|---|---|
| bit 0 | x¹ | leftmost end of the register (the LSB); the new feedback bit enters here |
| bit 13 | x¹⁴ | tap |
| bit 16 | x¹⁷ | tap |
| bit 17 | x¹⁸ | tap |
| bit 18 | x¹⁹ | tap, and also the **output bit** (the rightmost end, the MSB) |

**A point that causes confusion.** The specification's "left" is the left end of the register diagram, where bit 0 (x¹) sits. When a number is written in binary, the MSB is on the left, so bit 0 is the *rightmost* digit of the written number. In the tables below, binary states are written the usual way, **bit 18 first and bit 0 last**. The register "shifts toward the MSB", which in the written binary means every digit moves one place to the left, the leftmost digit falls out as the output, and the new feedback digit appears at the right end.

**1.2 One clock step**

1. **Output** = bit 18 of the current state (the digit at the left of the written binary).
2. **Feedback** = bit 13 ⊕ bit 16 ⊕ bit 17 ⊕ bit 18, read from the state *before* the shift. Bit 18 is both a tap and the output.
3. **New state** = shift the state one place toward the MSB, insert the feedback at bit 0, and keep only 19 bits. In integer terms: `((state << 1) | feedback) & 0x7FFFF`.

The constant term "1" in the polynomial is the connection that puts the feedback into bit 0. Nothing is inverted.

**1.3 Making a keystream byte**

Do 8 clock steps and collect the 8 output bits in order. The **first** output bit becomes bit 0 (the LSB) of the keystream byte, the second becomes bit 1, and so on, with the eighth becoming bit 7 (the MSB). The register is not touched between bytes. Byte 2 simply continues from the state where byte 1 stopped.

**1.4 Seed**

`0x67BD5` in 19 bits is `1100111101111010101`. That is bit 18 = 1, bit 17 = 1, bit 16 = 0, bit 15 = 0, bit 14 = 1, bit 13 = 1, and so on down to bit 0 = 1.

**1.5 Keystream byte 1, clock by clock**

"Binary" is the 19-bit state, bit 18 on the left and bit 0 on the right. The four tap columns are the values of bits 13, 16, 17 and 18 in that state.

| Clock | State (hex) | State (binary, bit 18 … bit 0) | b13 | b16 | b17 | b18 | Feedback = b13⊕b16⊕b17⊕b18 | Output = b18 | Next state (hex) |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `67BD5` | `1100111101111010101` | 1 | 0 | 1 | 1 | 1 | **1** | `4F7AB` |
| 2 | `4F7AB` | `1001111011110101011` | 1 | 0 | 0 | 1 | 0 | **1** | `1EF56` |
| 3 | `1EF56` | `0011110111101010110` | 1 | 1 | 0 | 0 | 0 | **0** | `3DEAC` |
| 4 | `3DEAC` | `0111101111010101100` | 0 | 1 | 1 | 0 | 0 | **0** | `7BD58` |
| 5 | `7BD58` | `1111011110101011000` | 1 | 1 | 1 | 1 | 0 | **1** | `77AB0` |
| 6 | `77AB0` | `1110111101010110000` | 1 | 1 | 1 | 1 | 0 | **1** | `6F560` |
| 7 | `6F560` | `1101111010101100000` | 1 | 0 | 1 | 1 | 1 | **1** | `5EAC1` |
| 8 | `5EAC1` | `1011110101011000001` | 1 | 1 | 0 | 1 | 1 | **1** | `3D583` |

**Worked clock 1 in full.**
- The state is `1100111101111010101`. Bit 18 = 1, bit 17 = 1, bit 16 = 0, bit 13 = 1.
- Output = 1.
- Feedback = 1 ⊕ 0 ⊕ 1 ⊕ 1 = 1. (b13 = 1, b16 = 0, b17 = 1, b18 = 1.)
- Shifting left one place gives `1001111011110101010` after dropping the old bit 18. Inserting the feedback 1 at bit 0 gives `1001111011110101011`, which is `4F7AB`.

**Assembling byte 1.** The outputs in order are 1, 1, 0, 0, 1, 1, 1, 1.

| Output number | 1st | 2nd | 3rd | 4th | 5th | 6th | 7th | 8th |
|---|---|---|---|---|---|---|---|---|
| Output bit | 1 | 1 | 0 | 0 | 1 | 1 | 1 | 1 |
| Goes to byte bit | 0 (LSB) | 1 | 2 | 3 | 4 | 5 | 6 | 7 (MSB) |

Written MSB first (bit 7 down to bit 0), the byte is `1 1 1 1 0 0 1 1` = `11110011` = **`0xF3`**. This is the first byte of the reference keystream.

**1.6 Keystream byte 2, clock by clock**

This continues from state `3D583`, with no re-seeding.

| Clock | State (hex) | State (binary, bit 18 … bit 0) | b13 | b16 | b17 | b18 | Feedback | Output = b18 | Next state (hex) |
|---|---|---|---|---|---|---|---|---|---|
| 9 | `3D583` | `0111101010110000011` | 0 | 1 | 1 | 0 | 0 | **0** | `7AB06` |
| 10 | `7AB06` | `1111010101100000110` | 1 | 1 | 1 | 1 | 0 | **1** | `7560C` |
| 11 | `7560C` | `1110101011000001100` | 0 | 1 | 1 | 1 | 1 | **1** | `6AC19` |
| 12 | `6AC19` | `1101010110000011001` | 1 | 0 | 1 | 1 | 1 | **1** | `55833` |
| 13 | `55833` | `1010101100000110011` | 0 | 1 | 0 | 1 | 0 | **1** | `2B066` |
| 14 | `2B066` | `0101011000001100110` | 1 | 0 | 1 | 0 | 0 | **0** | `560CC` |
| 15 | `560CC` | `1010110000011001100` | 1 | 1 | 0 | 1 | 1 | **1** | `2C199` |
| 16 | `2C199` | `0101100000110011001` | 0 | 0 | 1 | 0 | 1 | **0** | `58333` |

**Assembling byte 2.** The outputs in order are 0, 1, 1, 1, 1, 0, 1, 0.

| Output number | 1st | 2nd | 3rd | 4th | 5th | 6th | 7th | 8th |
|---|---|---|---|---|---|---|---|---|
| Output bit | 0 | 1 | 1 | 1 | 1 | 0 | 1 | 0 |
| Goes to byte bit | 0 (LSB) | 1 | 2 | 3 | 4 | 5 | 6 | 7 (MSB) |

Written MSB first, the byte is `0 1 0 1 1 1 1 0` = `01011110` = **`0x5E`**. This is the second byte of the reference keystream, and the register is left at `58333` ready for byte 3.

**1.7 Things that are easy to get wrong**

- **Reading the taps from the shifted state.** The feedback must come from the state *before* the shift. Using the shifted state gives a different, incompatible keystream.
- **Filling the byte MSB first.** The first output bit is the LSB. Reversing it turns `F3` into `CF`.
- **Treating "left" as the MSB.** In the spec, left is the x¹ end (bit 0). The output end is bit 18.
- **Re-seeding per byte or per chunk.** The register runs across the whole file.

2. The permutation
------------------

**2.1 The rule**

Positions in a byte are numbered 1 to 8, where position 1 is the MSB (value `0x80`) and position 8 is the LSB (value `0x01`). So position `p` has value 2^(8−p).

For an input byte x = (x₁, …, x₈), the output is y = (y₁, …, y₈) with

> **yᵢ = x_π(i)**   (output position i takes the input bit from position π(i))

| Output position i | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|
| π(i) = input position it takes | 2 | 6 | 3 | 5 | 1 | 8 | 4 | 7 |

Every input position appears exactly once in the second row, so no bit is lost or duplicated. That is what makes π a permutation and makes it reversible.

**2.2 Where each input bit goes**

The rule says where each output bit comes from. Reading it the other way round tells you where each input bit lands: input position j goes to the output position i for which π(i) = j.

| Input position j | Value | Lands at output position i (where π(i) = j) | Value there |
|---|---|---|---|
| 1 | `0x80` | 5 (because π(5) = 1) | `0x08` |
| 2 | `0x40` | 1 (π(1) = 2) | `0x80` |
| 3 | `0x20` | 3 (π(3) = 3) | `0x20` |
| 4 | `0x10` | 7 (π(7) = 4) | `0x02` |
| 5 | `0x08` | 4 (π(4) = 5) | `0x10` |
| 6 | `0x04` | 2 (π(2) = 6) | `0x40` |
| 7 | `0x02` | 8 (π(8) = 7) | `0x01` |
| 8 | `0x01` | 6 (π(6) = 8) | `0x04` |

Because the permutation only moves bits and never combines them, the output for any byte is the OR of the "Value there" entries for each input bit that is 1. For example `0x43` = `0x40` + `0x02` + `0x01`, so the output is `0x80 | 0x01 | 0x04` = `0x85`. This agrees with the worked "C" example in the design.

**2.3 Building the forward table**

For each byte value x from 0 to 255:

1. Pull out the eight bits x₁ … x₈ (x₁ is the MSB, so x_i = `(x >> (8 − i)) & 1`).
2. Form y₁ … y₈ using yᵢ = x_π(i).
3. Pack y₁ … y₈ back into a byte with y₁ as the MSB. The result is `PERM[x]`.

The table has 256 entries and is built once, when the module is loaded.

**2.4 Building the inverse**

The inverse undoes π. Decryption has a byte y and needs to find the x that produced it. From yᵢ = x_π(i), the bit that sat at input position π(i) is now at output position i. So to undo it, put y's bit i back at position π(i):

> **x_π(i) = yᵢ**

That is the same pairing of positions read in the other direction, so the inverse permutation π⁻¹ is simply "swap the two rows" of the π table.

**Step 1.** Write the pairs (i → π(i)) from the π table:

| i | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|
| π(i) | 2 | 6 | 3 | 5 | 1 | 8 | 4 | 7 |

**Step 2.** Swap the rows: each pair becomes (π(i) → i):

| π(i) | 2 | 6 | 3 | 5 | 1 | 8 | 4 | 7 |
|---|---|---|---|---|---|---|---|---|
| i = π⁻¹(π(i)) | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |

**Step 3.** Sort by the first row so it runs 1 to 8:

| j | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|
| π⁻¹(j) | 5 | 1 | 3 | 7 | 4 | 2 | 8 | 6 |

Reading it off: π(1) = 2, so π⁻¹(2) = 1. π(5) = 1, so π⁻¹(1) = 5. π(3) = 3, so π⁻¹(3) = 3. And so on. Checking the result: π⁻¹(π(i)) = i for every i.

This is the position-level inverse. The byte-level table is built in the design in a way that cannot disagree with it:

**Building `INV_PERM` for the 256 byte values.** After `PERM` is finished, for each x set `INV_PERM[PERM[x]] = x`. Because `PERM` is a bijection (each of the 256 outputs occurs exactly once), this fills every entry of `INV_PERM` exactly once. A unit test also checks the result against the π⁻¹ row above.

**Example.** `PERM[0x43] = 0x85`, so `INV_PERM[0x85] = 0x43`. Checking with the rule x_π(i) = yᵢ on y = `10000101` (y₁ … y₈ = 1, 0, 0, 0, 0, 1, 0, 1):
- x₂ = y₁ = 1, x₆ = y₂ = 0, x₃ = y₃ = 0, x₅ = y₄ = 0,
- x₁ = y₅ = 0, x₈ = y₆ = 1, x₄ = y₇ = 0, x₇ = y₈ = 1.
- So x = (x₁ … x₈) = 0, 1, 0, 0, 0, 0, 1, 1 = `01000011` = `0x43`.

3. Putting them together
------------------------

| Step | Encrypt | Decrypt |
|---|---|---|
| 1 | Take the next input byte | Take the next input byte |
| 2 | Look up `PERM[byte]` | XOR with the next keystream byte |
| 3 | XOR with the next keystream byte | Look up `INV_PERM[result]` |

The order matters. Encrypt permutes first and then XORs, so decrypt must XOR first (undoing the last step first) and then un-permute. Both directions use the same keystream because the register starts from the same seed and is clocked the same way.

Worked on the letter "C": encrypt `0x43` → `PERM` → `0x85` → ⊕ `0xF3` → **`0x76`**. Decrypt `0x76` → ⊕ `0xF3` → `0x85` → `INV_PERM` → **`0x43`**.
