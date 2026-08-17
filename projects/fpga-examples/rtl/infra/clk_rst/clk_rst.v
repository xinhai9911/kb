// -----------------------------------------------------------------------------
// clk_rst.v — 时钟与复位基础设施
//
// 异步复位、同步释放（Asynchronous Assert, Synchronous De-assert）
// 复位到来时立即生效（异步），撤销时经 2 级 FF 同步到 clk 域，
// 避免复位释放沿与时钟沿过近导致的亚稳态。
//
// 本骨架中 clk_out 直接透传 clk_in；真实工程此处接 PLL/MMCM。
// -----------------------------------------------------------------------------
`timescale 1ns / 1ps

module clk_rst (
    input  wire clk_in,       // 100 MHz 外部时钟
    input  wire rst_n_in,     // 异步复位，低有效
    output wire clk_out,      // 内部时钟
    output reg  rst_sync_n    // 同步释放后的复位，低有效
);

    reg rst_meta;

    always @(posedge clk_in or negedge rst_n_in) begin
        if (!rst_n_in)
            {rst_meta, rst_sync_n} <= 2'b00;
        else
            {rst_meta, rst_sync_n} <= {1'b1, rst_meta};
    end

    assign clk_out = clk_in;

endmodule
