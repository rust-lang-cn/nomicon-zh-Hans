# #[panic_handler]

`#[panic_handler]`用于定义`panic!`在`#![no_std]`程序中的行为。`#[panic_handler]`必须应用于签名为`fn(&PanicInfo) -> !`的函数，并且这样的函数仅能在一个二进制程序/动态链接库的整个依赖图中仅出现一次。`PanicInfo`的 API 可以在 [API docs] 中找到。

[API docs]: https://doc.rust-lang.org/core/panic/struct.PanicInfo.html

鉴于`#![no_std]`应用程序没有*标准*的输出，并且一些`#![no_std]`应用程序，例如嵌入式应用程序，在开发和发布时需要不同的 panic 行为，因此拥有专门的 panic crate，即只包含`#[panic_handler]`的 crate 是有帮助的。这样，应用程序可以通过简单地链接到一个不同的 panic crate 来轻松地选择 panic 行为。

下面是一个例子，根据使用开发配置文件（`cargo build`）或使用发布配置文件（`cargo build --release`）编译的应用程序具有不同的恐慌行为：

`panic-semihosting`crate —— 使用 semihosting 将 panic 信息记录到主机 stderr：

<!-- ignore: simplified code -->
```rust,ignore
#![no_std]

use core::fmt::{Write, self};
use core::panic::PanicInfo;

struct HStderr {
    // ..
#     _0: (),
}
#
# impl HStderr {
#     fn new() -> HStderr { HStderr { _0: () } }
# }
#
# impl fmt::Write for HStderr {
#     fn write_str(&mut self, _: &str) -> fmt::Result { Ok(()) }
# }

#[panic_handler]
fn panic(info: &PanicInfo) -> ! {
    let mut host_stderr = HStderr::new();

    // 输出日志: "panicked at '$reason', src/main.rs:27:4" 
    writeln!(host_stderr, "{}", info).ok();

    loop {}
}
```

`panic-halt`crate —— panic 时停止线程；消息被丢弃：

<!-- ignore: simplified code -->
```rust,ignore
#![no_std]

use core::panic::PanicInfo;

#[panic_handler]
fn panic(_info: &PanicInfo) -> ! {
    loop {}
}
```

`app` crate：

<!-- ignore: requires the above crates -->
```rust,ignore
#![no_std]

// dev profile
#[cfg(debug_assertions)]
extern crate panic_semihosting;

// release profile
#[cfg(not(debug_assertions))]
extern crate panic_halt;

fn main() {
    // ..
}
```
