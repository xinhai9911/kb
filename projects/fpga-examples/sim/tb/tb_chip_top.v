// -----------------------------------------------------------------------------
// tb_chip_top.v — 顶层 testbench
//
// 骨架健康检查：复位释放后跑 100us，统计 LED 翻转次数。
// N=10 时约每 10.24us 翻一次，100us 内应有 ~9 次 → 阈值取 5。
// -----------------------------------------------------------------------------
`timescale 1ns / 1ps

module tb_chip_top;

    reg        clk;
    reg        rst_n;
    wire [7:0] led;

    integer    toggle_cnt;
    reg  [7:0] led_prev;

    chip_top u_dut (
        .sys_clk   (clk),
        .sys_rst_n (rst_n),
        .led       (led)
    );

    initial clk = 1'b0;
    always #5 clk = ~clk;              // 100 MHz

    // 统计 LED 变化次数
    always @(posedge clk) begin
        if (rst_n) begin
            if (led !== led_prev)
                toggle_cnt = toggle_cnt + 1;
            led_prev = led;
        end
    end

    initial begin
        $dumpfile("sim/wave/tb_chip_top.vcd");
        $dumpvars(0, tb_chip_top);

        toggle_cnt = 0;
        led_prev   = 8'h00;
        rst_n      = 1'b0;

        #200;
        rst_n = 1'b1;                  // 200ns 后释放复位

        #100_000;                      // 跑 100us

        if (toggle_cnt >= 5) begin
            $display("[PASS] led toggled %0d times in 100us", toggle_cnt);
            $finish;
        end else begin
            $display("[FAIL] led toggled only %0d times", toggle_cnt);
            $fatal(1);          // 非零退出码，让 sim.sh 能感知失败
        end
    end

endmodule
