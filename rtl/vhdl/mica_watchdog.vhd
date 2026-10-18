-- Windowed watchdog, deliberately separate from the processor datapath.
-- Type checking helps keep unsigned counters and logic controls apart.
-- The system must connect expired to an actual reset/interrupt policy.
-- SPDX-License-Identifier: MIT
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity mica_watchdog is
  generic (COUNT_WIDTH : positive := 32);
  port (
    clk_i       : in  std_logic;
    rst_ni      : in  std_logic;
    enable_i    : in  std_logic;
    kick_i      : in  std_logic;
    clear_i     : in  std_logic := '0';
    min_ticks_i : in  unsigned(COUNT_WIDTH-1 downto 0);
    max_ticks_i : in  unsigned(COUNT_WIDTH-1 downto 0);
    expired_o   : out std_logic;
    early_o     : out std_logic;
    count_o     : out unsigned(COUNT_WIDTH-1 downto 0)
  );
end entity;

architecture rtl of mica_watchdog is
  signal count   : unsigned(COUNT_WIDTH-1 downto 0);
  signal expired : std_logic := '0';
  signal early   : std_logic := '0';
  signal counter_clear, counter_enable, kick_ok : std_logic;
begin
  expired_o <= expired;
  early_o <= early;
  count_o <= count;
  kick_ok <= '1' when kick_i = '1' and count >= min_ticks_i and
      count < max_ticks_i and min_ticks_i < max_ticks_i and
      expired = '0' and early = '0' else '0';
  counter_clear <= clear_i or not enable_i or kick_ok;
  counter_enable <= enable_i and not expired and not early;
  elapsed: entity work.mica_event_counter
    generic map (COUNT_WIDTH => COUNT_WIDTH, SATURATE => true)
    port map (clk_i => clk_i, rst_ni => rst_ni, enable_i => counter_enable,
      event_i => '1', clear_i => counter_clear, count_o => count, overflow_o => open);

  process(clk_i, rst_ni)
  begin
    if rst_ni = '0' then
      expired <= '0';
      early <= '0';
    elsif rising_edge(clk_i) then
      if clear_i = '1' then
        expired <= '0';
        early <= '0';
      elsif enable_i = '1' and expired = '0' and early = '0' then
        if max_ticks_i = to_unsigned(0, COUNT_WIDTH) or
           min_ticks_i >= max_ticks_i or count >= max_ticks_i then
          expired <= '1';
        elsif kick_i = '1' then
          if count < min_ticks_i then
            early <= '1';
          end if;
        elsif count >= max_ticks_i - 1 then
          expired <= '1';
        end if;
      end if;
    end if;
  end process;
end architecture;
