library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use std.env.all;

entity tb_mica_event_counter is end;
architecture tb of tb_mica_event_counter is
  signal clk : std_logic := '0';
  signal rst_n, en, event, clear : std_logic := '0';
  signal saturated, wrapped : unsigned(2 downto 0);
  signal sat_overflow, wrap_overflow : std_logic;
begin
  clk <= not clk after 5 ns;
  sat: entity work.mica_event_counter generic map (3, true)
    port map (clk, rst_n, en, event, clear, saturated, sat_overflow);
  wrap: entity work.mica_event_counter generic map (3, false)
    port map (clk, rst_n, en, event, clear, wrapped, wrap_overflow);
  process
    variable s, w : natural := 0;
    variable so, wo : std_logic := '0';
  begin
    wait for 12 ns;
    assert saturated = 0 and wrapped = 0 severity failure;
    rst_n <= '1';
    for i in 0 to 127 loop
      en <= '1'; event <= '1'; clear <= '0';
      if i mod 19 = 0 then
        clear <= '1'; en <= '0'; s := 0; w := 0; so := '0'; wo := '0';
      elsif i mod 17 = 0 then
        en <= '0';
      elsif i mod 13 = 0 then
        event <= '0';
      else
        if s = 7 then so := '1'; else s := s + 1; end if;
        if w = 7 then wo := '1'; w := 0; else w := w + 1; end if;
      end if;
      wait until rising_edge(clk); wait for 1 ns;
      assert saturated = s and wrapped = w and sat_overflow = so and wrap_overflow = wo
        report "event counter model mismatch" severity failure;
    end loop;
    rst_n <= '0'; wait for 1 ns;
    assert saturated = 0 and wrapped = 0 and sat_overflow = '0' and wrap_overflow = '0'
      report "event counter reset" severity failure;
    report "mica_event_counter PASS: wrap, saturation, enable, clear, reset" severity note;
    finish;
  end process;
  process begin wait for 5 us; assert false report "event counter timeout" severity failure; end process;
end architecture;
