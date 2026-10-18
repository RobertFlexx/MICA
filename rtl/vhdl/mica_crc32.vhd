-- CRC-32/ISO-HDLC: reflected polynomial EDB88320, init/xorout FFFFFFFF.
-- Eight clocks per accepted byte. crc_o changes only when a byte completes.
-- clear_i cancels an unfinished byte and starts a new message.
-- SPDX-License-Identifier: MIT
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity mica_crc32 is
  port (
    clk_i, rst_ni, clear_i : in std_logic;
    byte_valid_i : in std_logic;
    byte_ready_o : out std_logic;
    byte_i : in unsigned(7 downto 0);
    busy_o : out std_logic;
    crc_o, count_o : out unsigned(31 downto 0)
  );
end entity;

architecture rtl of mica_crc32 is
  constant POLYNOMIAL : unsigned(31 downto 0) := x"EDB88320";
  signal committed, working : unsigned(31 downto 0);
  signal count : unsigned(31 downto 0);
  signal busy : std_logic;
  signal bit_index : unsigned(2 downto 0);
begin
  byte_ready_o <= not busy and not clear_i and rst_ni;
  busy_o <= busy;
  crc_o <= not committed;
  count_o <= count;
  process(clk_i, rst_ni)
    variable next_crc : unsigned(31 downto 0);
  begin
    if rst_ni = '0' then
      committed <= (others => '1');
      working <= (others => '1');
      count <= (others => '0');
      bit_index <= (others => '0');
      busy <= '0';
    elsif rising_edge(clk_i) then
      if clear_i = '1' then
        committed <= (others => '1');
        working <= (others => '1');
        count <= (others => '0');
        bit_index <= (others => '0');
        busy <= '0';
      elsif busy = '1' then
        next_crc := shift_right(working, 1);
        if working(0) = '1' then
          next_crc := next_crc xor POLYNOMIAL;
        end if;
        working <= next_crc;
        if bit_index = 7 then
          committed <= next_crc;
          count <= count + 1; -- Completed-byte count wraps modulo 2**32.
          busy <= '0';
        else
          bit_index <= bit_index + 1;
        end if;
      elsif byte_valid_i = '1' then
        working <= committed xor resize(byte_i, 32);
        bit_index <= (others => '0');
        busy <= '1';
      end if;
    end if;
  end process;
end architecture;
