// -----------------------------------------------------------------------------
// led_blink.v — LED 跑马灯
//
// 计数器分频，每 2^N 个时钟周期把 8 位 LED 循环左移一位。
// N 通过 parameter 可调：上板用 26（100MHz 下约 671ms），仿真用 20（约 10.5us）。
// -----------------------------------------------------------------------------
`timescale 1ns / 1ps

module led_blink #(
    parameter N = 26
) (
    input  wire       clk,
    input  wire       rst_n,     // 异步复位，低有效
    output reg  [7:0] led
);

    reg [N-1:0] cnt;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            cnt <= {N{1'b0}};
            led <= 8'b0000_0001;
        end else if (cnt == {N{1'b1}}) begin
            cnt <= {N{1'b0}};
            led <= {led[6:0], led[7]};   // 循环左移
        end else begin
            cnt <= cnt + 1'b1;
        end
    end

endmodule
