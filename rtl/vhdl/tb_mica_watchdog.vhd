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
  signal clear : std_logic := '0';
  signal minimum : unsigned(7 downto 0) := to_unsigned(2, 8);
  signal maximum : unsigned(7 downto 0) := to_unsigned(8, 8);
  signal expired, early : std_logic;
  signal n : unsigned(7 downto 0);
begin
  clk <= not clk after 5 ns;
  dut: entity work.mica_watchdog
    generic map (COUNT_WIDTH => 8)
    port map (
      clk_i => clk, rst_ni => rst_n, enable_i => en,
      kick_i => kick, clear_i => clear, min_ticks_i => minimum,
      max_ticks_i => maximum, expired_o => expired,
      early_o => early, count_o => n
    );
  process
    procedure tick is
    begin wait until rising_edge(clk); wait for 1 ns; end procedure;
  begin
    wait for 12 ns;
    rst_n <= '1'; en <= '1';
    tick; tick; tick;
    assert n = 3 report "counter didn't advance" severity failure;
    kick <= '1';
    tick;
    assert n = to_unsigned(0,8) report "valid watchdog kick failed" severity failure;
    kick <= '0';
    for i in 1 to 8 loop tick; end loop;
    assert expired = '1' report "watchdog didn't expire" severity failure;
    kick <= '1'; en <= '0'; tick;
    assert expired = '1' and n = 0 report "disable cleared sticky fault" severity failure;
    clear <= '1'; tick; clear <= '0'; en <= '1';
    kick <= '1'; tick;
    assert early = '1' report "early kick accepted" severity failure;
    kick <= '0'; clear <= '1'; tick; clear <= '0';
    for i in 1 to 5 loop tick; end loop;
    maximum <= to_unsigned(4, 8); kick <= '1'; tick;
    assert expired = '1' report "late kick after deadline reprogramming accepted" severity failure;
    clear <= '1'; kick <= '0'; tick; clear <= '0';
    maximum <= minimum; tick;
    assert expired = '1' report "empty watchdog window accepted" severity failure;
    clear <= '1'; tick; clear <= '0'; maximum <= (others => '0'); tick;
    assert expired = '1' report "zero watchdog deadline accepted" severity failure;
    rst_n <= '0'; wait for 1 ns;
    assert early = '0' and expired = '0' and n = 0 report "watchdog reset" severity failure;
    report "mica_watchdog PASS: windows, late kick, clear, sticky faults, reset" severity note;
    finish;
  end process;
  process begin wait for 5 us; assert false report "watchdog timeout" severity failure; end process;
end architecture;
