"""Independent Python re-implementation of the rram_cell RTL + stochastic TB stimulus.
Purpose: bit-exact golden model, so parameter sweeps and entropy studies can run in
seconds instead of a Vivado round-trip. Verified against RRAM.sim output bit-for-bit.
"""

IDLE, SET, READ_SET, UPDATE_SET, RESET, READ_RESET, UPDATE_RESET = range(7)

def lfsr_next(v):
    """taps 7,5,4,3 -> x^8+x^6+x^5+x^4+1, maximal length 255"""
    return ((v << 1) & 0xFF) | (((v >> 7) ^ (v >> 5) ^ (v >> 4) ^ (v >> 3)) & 1)

def fsm_next(state, enable):
    if state == IDLE:         return SET if enable else IDLE
    if state == SET:          return READ_SET
    if state == READ_SET:     return UPDATE_SET
    if state == UPDATE_SET:   return RESET
    if state == RESET:        return READ_RESET
    if state == READ_RESET:   return UPDATE_RESET
    if state == UPDATE_RESET: return SET if enable else IDLE
    return IDLE

def fsm_out(state):
    """returns (do_set, do_reset, do_read, do_update)"""
    return (state == SET, state == RESET,
            state in (READ_SET, READ_RESET),
            state in (UPDATE_SET, UPDATE_RESET))

def cycle_variation(cur, rand, lo=80, hi=180):
    sel = rand & 0b11
    if sel == 0b00: return cur - 1 if cur > lo else cur
    if sel == 0b10: return cur + 1 if cur < hi else cur
    return cur

def run(n_samples=100000, set_thr=145, reset_thr=110, noise_thr=96,
        seeds=(0b10110101, 0b11001011, 0b11100011, 0b10010111),
        pre_advance=0, rand_stream=None, trace=False):
    """rand_stream: optional iterator yielding 4-tuples, replacing the LFSRs entirely."""
    ls, lr, ln, lv = seeds
    rs, rr, rn, rv = seeds
    for _ in range(pre_advance):
        ls, lr, ln, lv = lfsr_next(ls), lfsr_next(lr), lfsr_next(ln), lfsr_next(lv)
        rs, rr, rn, rv = ls, lr, ln, lv

    state, rram, prev = IDLE, 0, 0
    st, rt, nt = set_thr, reset_thr, noise_thr
    bits, tr = [], []
    cycles = 0
    while len(bits) < n_samples:
        cycles += 1
        # --- combinational, pre-edge ---
        do_set, do_reset, do_read, do_update = fsm_out(state)
        set_ok, reset_ok = rs < st, rr < rt
        # --- posedge: register updates ---
        nstate = fsm_next(state, True)
        nprev, nrram = rram, rram
        if do_set and set_ok:       nrram = 1
        elif do_reset and reset_ok: nrram = 0
        if do_update:
            st, rt = cycle_variation(st, rv), cycle_variation(rt, rv)
        state, prev, rram = nstate, nprev, nrram
        # --- combinational, post-edge (what the TB's #1 sampler observes) ---
        _, _, do_read_p, _ = fsm_out(state)
        transition = prev ^ rram
        flip = rn < nt
        if do_read_p:
            bits.append(transition ^ flip)
            if trace: tr.append((cycles, st, rt, rram, transition, int(flip)))
        # --- negedge: advance stimulus ---
        if rand_stream is not None:
            rs, rr, rn, rv = next(rand_stream)
        else:
            ls, lr, ln, lv = lfsr_next(ls), lfsr_next(lr), lfsr_next(ln), lfsr_next(lv)
            rs, rr, rn, rv = ls, lr, ln, lv
    return (bits, cycles, tr) if trace else (bits, cycles)
