library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use std.env.all;

entity tb_mica_watchdog is end;
architecture tb of tb_mica_watchdog is
  signal clk : std_logic := '0';
  signal rst_n : std_logic := '0';
  signal en : std_logic := '0';
  signal kick : std_logic := '0';
  signal expired, early : std_logic;
  signal n : unsigned(7 downto 0);
begin
  clk <= not clk after 5 ns;
  dut: entity work.mica_watchdog
    generic map (COUNT_WIDTH => 8)
    port map (
      clk_i => clk, rst_ni => rst_n, enable_i => en,
      kick_i => kick, min_ticks_i => to_unsigned(2, 8),
      max_ticks_i => to_unsigned(8, 8), expired_o => expired,
      early_o => early, count_o => n
    );
  process
  begin
    wait for 12 ns;
    rst_n <= '1'; en <= '1';
    wait until rising_edge(clk);
    wait until rising_edge(clk);
    wait until rising_edge(clk);
    wait for 1 ns;
    assert n >= to_unsigned(2,8) report "counter didn't advance" severity failure;
    kick <= '1';
    wait until rising_edge(clk);
    wait for 1 ns;
    assert n = to_unsigned(0,8) report "valid watchdog kick failed" severity failure;
    kick <= '0';
    wait for 100 ns;
    assert expired = '1' report "watchdog didn't expire" severity failure;
    report "mica_watchdog PASS" severity note;
    finish;
  end process;
end architecture;
