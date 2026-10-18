-- Synchronous event accumulator. Clear has priority; overflow is sticky.
-- Events must already be synchronous to clk_i. Saturation is optional.
-- SPDX-License-Identifier: MIT
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity mica_event_counter is
  generic (COUNT_WIDTH : positive := 32; SATURATE : boolean := true);
  port (
    clk_i, rst_ni, enable_i, event_i, clear_i : in std_logic;
    count_o : out unsigned(COUNT_WIDTH-1 downto 0);
    overflow_o : out std_logic
  );
end entity;

architecture rtl of mica_event_counter is
  constant MAX_COUNT : unsigned(COUNT_WIDTH-1 downto 0) := (others => '1');
  signal count : unsigned(COUNT_WIDTH-1 downto 0);
  signal overflow : std_logic;
begin
  count_o <= count;
  overflow_o <= overflow;
  process(clk_i, rst_ni)
  begin
    if rst_ni = '0' then
      count <= (others => '0');
      overflow <= '0';
    elsif rising_edge(clk_i) then
      if clear_i = '1' then
        count <= (others => '0');
        overflow <= '0';
      elsif enable_i = '1' and event_i = '1' then
        if count = MAX_COUNT then
          overflow <= '1';
          if not SATURATE then count <= (others => '0'); end if;
        else
          count <= count + 1;
        end if;
      end if;
    end if;
  end process;
end architecture;
