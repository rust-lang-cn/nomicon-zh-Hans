# 标准库之下

本节记录了（或将记录）`#![no_std]`开发人员必须处理（即提供）由标准库提供的功能，来构建`#![no_std]`的 Rust 二进制程序。下面是一个（可能是不完整的）此类功能的列表：

- `#[lang = "eh_personality"]`
- `#[lang = "start"]`
- `#[lang = "termination"]`
- `#[panic_implementation]`
