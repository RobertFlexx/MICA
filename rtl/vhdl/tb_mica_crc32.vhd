library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use std.env.all;
entity tb_mica_crc32 is end;
architecture tb of tb_mica_crc32 is
  signal clk : std_logic := '0';
  signal rst_n, clear, valid : std_logic := '0';
  signal ready, busy : std_logic;
  signal data : unsigned(7 downto 0) := (others => '0');
  signal crc, count : unsigned(31 downto 0);
  -- Independent reference: MSB-first polynomial with reversed input/output bits.
  function reference_step(state : unsigned; b : unsigned) return unsigned is
    variable n : unsigned(31 downto 0) := state;
    variable feedback : std_logic;
  begin
    for i in 0 to 7 loop
      feedback := n(31) xor b(i);
      n := shift_left(n, 1);
      if feedback = '1' then n := n xor x"04C11DB7"; end if;
    end loop;
    return n;
  end function;
  function finalized(state : unsigned) return unsigned is
    variable n : unsigned(31 downto 0);
  begin
    for i in 0 to 31 loop n(i) := not state(31-i); end loop;
    return n;
  end function;
begin
  clk <= not clk after 5 ns;
  dut: entity work.mica_crc32 port map(clk, rst_n, clear, valid, ready, data, busy, crc, count);
  process
    variable ref : unsigned(31 downto 0) := (others => '1');
    variable prior : unsigned(31 downto 0);
    variable b : unsigned(7 downto 0);
    procedure send(value : natural) is
    begin
      wait until falling_edge(clk);
      assert ready = '1' report "CRC not ready" severity failure;
      valid <= '1'; data <= to_unsigned(value, 8);
      wait until falling_edge(clk);
      valid <= '0';
    end procedure;
  begin
    wait for 12 ns; rst_n <= '1';
    wait until falling_edge(clk);
    assert crc = x"00000000" and count = 0 report "empty CRC" severity failure;
    for i in 1 to 9 loop
      send(48+i);
      prior := crc;
      -- A new byte presented while busy must not change the committed result.
      data <= x"FF"; valid <= '1';
      for bit_no in 0 to 6 loop
        wait until falling_edge(clk);
        assert crc = prior and ready = '0' report "CRC changed before completion" severity failure;
      end loop;
      valid <= '0';
      wait until falling_edge(clk);
      assert ready = '1' and count = i report "CRC byte timing/count" severity failure;
    end loop;
    assert crc = x"CBF43926" report "CRC check vector" severity failure;
    clear <= '1'; wait until falling_edge(clk); clear <= '0';
    for i in 0 to 255 loop
      b := to_unsigned((i*73+19) mod 256, 8);
      send(to_integer(b));
      ref := reference_step(ref,b);
      for j in 1 to 8 loop wait until falling_edge(clk); end loop;
      assert crc = finalized(ref) and count = i+1 report "CRC independent reference" severity failure;
    end loop;
    send(42); -- Cancel an unfinished byte, including a simultaneous valid input.
    clear <= '1'; valid <= '1';
    wait until falling_edge(clk); clear <= '0'; valid <= '0';
    assert crc = 0 and count = 0 and busy = '0' report "CRC clear while busy" severity failure;
    send(99); rst_n <= '0'; wait for 1 ns;
    assert crc = 0 and count = 0 and busy = '0' report "CRC asynchronous reset" severity failure;
    report "mica_crc32 PASS: check vector, independent 256-byte stream, stalls, clear, reset" severity note;
    finish;
  end process;
end architecture;
