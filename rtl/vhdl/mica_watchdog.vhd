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
    min_ticks_i : in  unsigned(COUNT_WIDTH-1 downto 0);
    max_ticks_i : in  unsigned(COUNT_WIDTH-1 downto 0);
    expired_o   : out std_logic;
    early_o     : out std_logic;
    count_o     : out unsigned(COUNT_WIDTH-1 downto 0)
  );
end entity;

architecture rtl of mica_watchdog is
  signal count   : unsigned(COUNT_WIDTH-1 downto 0) := (others => '0');
  signal expired : std_logic := '0';
  signal early   : std_logic := '0';
begin
  expired_o <= expired;
  early_o <= early;
  count_o <= count;

  process(clk_i, rst_ni)
  begin
    if rst_ni = '0' then
      count <= (others => '0');
      expired <= '0';
      early <= '0';
    elsif rising_edge(clk_i) then
      if enable_i = '0' then
        count <= (others => '0');
      elsif expired = '0' and early = '0' then
        if max_ticks_i = to_unsigned(0, COUNT_WIDTH) or
           min_ticks_i >= max_ticks_i then
          expired <= '1';  -- Bad programming is not a free pass.
        elsif kick_i = '1' then
          if count < min_ticks_i then
            early <= '1';
          else
            count <= (others => '0');
          end if;
        elsif count >= max_ticks_i - 1 then
          expired <= '1';
        else
          count <= count + 1;
        end if;
      end if;
    end if;
  end process;
end architecture;
