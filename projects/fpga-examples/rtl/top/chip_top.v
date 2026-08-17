// -----------------------------------------------------------------------------
// chip_top.v — 芯片顶层
//
// 骨架顶层：时钟复位基础设施 + 一个跑马灯负载。
// 后续新增模块统一在此例化并连线。
// -----------------------------------------------------------------------------
`timescale 1ns / 1ps

module chip_top (
    input  wire       sys_clk,     // 100 MHz 外部晶振
    input  wire       sys_rst_n,   // 异步复位按键，低有效
    output wire [7:0] led
);

    wire clk_int;
    wire rst_sync_n;

    clk_rst u_clk_rst (
        .clk_in     (sys_clk),
        .rst_n_in   (sys_rst_n),
        .clk_out    (clk_int),
        .rst_sync_n (rst_sync_n)
    );

    // N=10：仿真加速。2^10 / 100MHz = 1024 × 10ns ≈ 10.24us 翻一次，
    // 100us 窗口内可翻 ~9 次。上板改回 26（≈671ms，肉眼可见）。
    led_blink #(
        .N (10)
    ) u_led_blink (
        .clk   (clk_int),
        .rst_n (rst_sync_n),
        .led   (led)
    );

endmodule
