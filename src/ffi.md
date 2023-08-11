# 外部函数接口（FFI）

## 简介

本指南将使用[snappy](https://github.com/google/snappy)压缩/解压缩库作为为外部代码编写绑定的示例。Rust 目前无法直接调用 C++ 库，但 snappy 包括一个 C 接口（在[`snappy-c.h`](https://github.com/google/snappy/blob/master/snappy-c.h)）。

## 关于 libc 的说明

这些例子中有许多使用了[the `libc` crate][libc]，它为 C 类型提供了各种类型定义，以及其他东西。如果你要自己尝试这些例子, 你需要在你的`Cargo.toml`中加入`libc`：

```toml
[dependencies]
libc = "0.2.0"
```

[libc]: https://crates.io/crates/libc

## 调用外部函数

下面是一个调用外部函数的最小例子，如果你安装了 snappy，它就可以被编译：

<!-- ignore: requires libc crate -->

```rust,ignore
use libc::size_t;

#[link(name = "snappy")]
extern {
    fn snappy_max_compressed_length(source_length: size_t) -> size_t;
}

fn main() {
    let x = unsafe { snappy_max_compressed_length(100) };
    println!("max compressed length of a 100 byte buffer: {}", x);
}
```

`extern`块是一个外部库中的函数签名列表，在本例中是平台的 C ABI。`#[link(...)]`属性用来指示链接器与 snappy 库进行链接，以便解析这些符号。

外部函数被认为是不安全的，所以对它们的调用需要用`unsafe {}`来包装，作为对编译器的承诺，其中包含的所有内容都是安全的。C 库经常暴露出不是线程安全的接口，而且几乎所有接受指针参数的函数都对一些输入是无效的，因为指针可能是悬空的，而原始指针不在 Rust 的安全内存模型之内。

当声明一个外部函数的参数类型时，Rust 编译器不能检查声明是否正确，所以正确指定它是在运行时保持绑定正确的一部分。

`extern`块可以被扩展到覆盖整个 snappy API：

<!-- ignore: requires libc crate -->

```rust,ignore
use libc::{c_int, size_t};

#[link(name = "snappy")]
extern {
    fn snappy_compress(input: *const u8,
                       input_length: size_t,
                       compressed: *mut u8,
                       compressed_length: *mut size_t) -> c_int;
    fn snappy_uncompress(compressed: *const u8,
                         compressed_length: size_t,
                         uncompressed: *mut u8,
                         uncompressed_length: *mut size_t) -> c_int;
    fn snappy_max_compressed_length(source_length: size_t) -> size_t;
    fn snappy_uncompressed_length(compressed: *const u8,
                                  compressed_length: size_t,
                                  result: *mut size_t) -> c_int;
    fn snappy_validate_compressed_buffer(compressed: *const u8,
                                         compressed_length: size_t) -> c_int;
}
# fn main() {}
```

## 创建一个安全的接口

原始的 C 语言 API 需要被包装起来，以提供内存安全，并使用更高级别的概念，如向量。一个库可以选择只公开安全的高级接口而隐藏不安全的内部细节。

封装一个需要内存 buffer 参数的函数需要使用`slice::raw`模块来操作 Rust Vec 作为内存的指针。Rust 的 Vec 被保证为一个连续的内存块，长度是当前包含的元素数，容量是分配的内存的总大小（元素），其中长度必定小于或等于容量：

<!-- ignore: requires libc crate -->

```rust,ignore
# use libc::{c_int, size_t};
# unsafe fn snappy_validate_compressed_buffer(_: *const u8, _: size_t) -> c_int { 0 }
# fn main() {}
pub fn validate_compressed_buffer(src: &[u8]) -> bool {
    unsafe {
        snappy_validate_compressed_buffer(src.as_ptr(), src.len() as size_t) == 0
    }
}
```

上面的“validate_compressed_buffer”包装器使用了一个“unsafe”块，但它通过在函数签名中去掉“unsafe”来保证调用它对所有输入都是安全的。

`snappy_compress`和`snappy_uncompress`函数更复杂，因为还需要分配一个缓冲区来容纳输出。

`snappy_max_compressed_length`函数可以用来分配一个最大容量的 Vec，以容纳压缩后的输出，然后该向量可以作为输出参数传递给`snappy_compress`函数。还会传递一个输出参数来检索压缩后的真实长度，以便设置长度：

<!-- ignore: requires libc crate -->

```rust,ignore
# use libc::{size_t, c_int};
# unsafe fn snappy_compress(a: *const u8, b: size_t, c: *mut u8,
#                           d: *mut size_t) -> c_int { 0 }
# unsafe fn snappy_max_compressed_length(a: size_t) -> size_t { a }
# fn main() {}
pub fn compress(src: &[u8]) -> Vec<u8> {
    unsafe {
        let srclen = src.len() as size_t;
        let psrc = src.as_ptr();

        let mut dstlen = snappy_max_compressed_length(srclen);
        let mut dst = Vec::with_capacity(dstlen as usize);
        let pdst = dst.as_mut_ptr();

        snappy_compress(psrc, srclen, pdst, &mut dstlen);
        dst.set_len(dstlen as usize);
        dst
    }
}
```

解压缩也是类似的，因为 snappy 将未压缩的大小作为压缩格式的一部分来存储，`snappy_uncompressed_length`将检索出所需的确切缓冲区大小：

<!-- ignore: requires libc crate -->

```rust,ignore
# use libc::{size_t, c_int};
# unsafe fn snappy_uncompress(compressed: *const u8,
#                             compressed_length: size_t,
#                             uncompressed: *mut u8,
#                             uncompressed_length: *mut size_t) -> c_int { 0 }
# unsafe fn snappy_uncompressed_length(compressed: *const u8,
#                                      compressed_length: size_t,
#                                      result: *mut size_t) -> c_int { 0 }
# fn main() {}
pub fn uncompress(src: &[u8]) -> Option<Vec<u8>> {
    unsafe {
        let srclen = src.len() as size_t;
        let psrc = src.as_ptr();

        let mut dstlen: size_t = 0;
        snappy_uncompressed_length(psrc, srclen, &mut dstlen);

        let mut dst = Vec::with_capacity(dstlen as usize);
        let pdst = dst.as_mut_ptr();

        if snappy_uncompress(psrc, srclen, pdst, &mut dstlen) == 0 {
            dst.set_len(dstlen as usize);
            Some(dst)
        } else {
            None // SNAPPY_INVALID_INPUT
        }
    }
}
```

然后，我们可以添加一些测试来展示如何使用它们：

<!-- ignore: requires libc crate -->

```rust,ignore
# use libc::{c_int, size_t};
# unsafe fn snappy_compress(input: *const u8,
#                           input_length: size_t,
#                           compressed: *mut u8,
#                           compressed_length: *mut size_t)
#                           -> c_int { 0 }
# unsafe fn snappy_uncompress(compressed: *const u8,
#                             compressed_length: size_t,
#                             uncompressed: *mut u8,
#                             uncompressed_length: *mut size_t)
#                             -> c_int { 0 }
# unsafe fn snappy_max_compressed_length(source_length: size_t) -> size_t { 0 }
# unsafe fn snappy_uncompressed_length(compressed: *const u8,
#                                      compressed_length: size_t,
#                                      result: *mut size_t)
#                                      -> c_int { 0 }
# unsafe fn snappy_validate_compressed_buffer(compressed: *const u8,
#                                             compressed_length: size_t)
#                                             -> c_int { 0 }
# fn main() { }
#
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn valid() {
        let d = vec![0xde, 0xad, 0xd0, 0x0d];
        let c: &[u8] = &compress(&d);
        assert!(validate_compressed_buffer(c));
        assert!(uncompress(c) == Some(d));
    }

    #[test]
    fn invalid() {
        let d = vec![0, 0, 0, 0];
        assert!(!validate_compressed_buffer(&d));
        assert!(uncompress(&d).is_none());
    }

    #[test]
    fn empty() {
        let d = vec![];
        assert!(!validate_compressed_buffer(&d));
        assert!(uncompress(&d).is_none());
        let c = compress(&d);
        assert!(validate_compressed_buffer(&c));
        assert!(uncompress(&c) == Some(d));
    }
}
```

## 析构器

外部的库经常把资源的所有权交给调用代码，当这种情况发生时，我们必须使用 Rust 的析构器来提供安全并保证这些资源的释放（尤其是在 panic 的情况下）。

关于析构器的更多信息，请参见 [Drop trait](https://doc.rust-lang.org/stable/std/ops/trait.Drop.html)。

## 从 C 调用 Rust 代码

你可能想要把 Rust 代码编译成某种形式，以便在 C 中调用。这个并不难，不过需要一些额外的步骤。

### Rust 代码侧

首先，我们假设你有一个 lib 库名字叫`rust_from_c`，其中的`lib.rs`应该包含类似这样的代码：

```rust
#[no_mangle]
pub extern "C" fn hello_from_rust() {
    println!("Hello from Rust!");
}
# fn main() {}
```

`extern "C"`使得这个函数使用 C 的调用规约，正如下文[外部调用规约]一章所述。
`no_mangle`属性关闭了 Rust 的 name mangling 特性，这使得我们在链接时有个明确定义的符号名。

接下来，为了把我们的 Rust 代码编译成一个可以直接从 C 调用的共享库，我们需要加这些到`Cargo.toml`中：

```toml
[lib]
crate-type = ["cdylib"]
```

（注意：我们也可以用`staticlib`类型，不过这会需要我们修改一些链接的参数。）

接下来，执行`cargo build`，Rust 侧就搞定啦！

[外部调用规约]: ffi.md#外部调用规约

### C 代码侧

我们将写一段 C 代码来调用`hello_from_rust`并用`gcc`来编译。

C 代码大致是这样：

```c
extern void hello_from_rust();

int main(void) {
    hello_from_rust();
    return 0;
}
```

我们把这个文件命名为`call_rust.c`，并且把它放到我们 crate 的根目录下，然后编译：

```sh
gcc call_rust.c -o call_rust -lrust_from_c -L./target/debug
```

`-l`和`-L`告诉 gcc 去找我们的 Rust 库。

最后，我们可以通过指定`LD_LIBRARY_PATH`来从 C 调用 Rust：

```sh
$ LD_LIBRARY_PATH=./target/debug ./call_rust
Hello from Rust!
```

搞定！
如果需要更多实际的例子，可以参考[`cbindgen`]。

[`cbindgen`]: https://github.com/eqrion/cbindgen

## 从 C 代码到 Rust 函数的回调

一些外部库需要使用回调来向调用者报告其当前状态或中间数据，我们可以将 Rust 中定义的函数传递给外部库。这方面的要求是，回调函数被标记为“extern”，并有正确的调用约定，使其可以从 C 代码中调用。

然后，回调函数可以通过注册调用发送到 C 库中，之后再从那里调用。

一个基本的例子是：

Rust 代码：

```rust,no_run
extern fn callback(a: i32) {
    println!("I'm called from C with value {0}", a);
}

#[link(name = "extlib")]
extern {
   fn register_callback(cb: extern fn(i32)) -> i32;
   fn trigger_callback();
}

fn main() {
    unsafe {
        register_callback(callback);
        trigger_callback(); // 触发回调
    }
}
```

C 代码：

```c
typedef void (*rust_callback)(int32_t);
rust_callback cb;

int32_t register_callback(rust_callback callback) {
    cb = callback;
    return 1;
}

void trigger_callback() {
  cb(7); // 在 Rust 中会调用回调函数 callback(7)
}
```

在这个例子中，Rust 的`main()`将调用 C 语言中的`trigger_callback()`，而这又会回调 Rust 中的`callback()`。

## 针对 Rust 对象的回调

前面的例子展示了如何从 C 代码中调用一个全局函数，然而，人们通常希望回调是针对一个特殊的 Rust 对象，这可能是代表相应的 C 对象的封装器的对象。

这可以通过向 C 库传递一个指向该对象的原始指针来实现，然后，C 库可以在通知中包含指向 Rust 对象的指针，这将使回调能够不安全地访问引用的 Rust 对象。

Rust 代码：

```rust,no_run
struct RustObject {
    a: i32,
    // 其余的成员...
}

extern "C" fn callback(target: *mut RustObject, a: i32) {
    println!("I'm called from C with value {0}", a);
    unsafe {
        // 在回调函数中更新 RustObject 的内容
        (*target).a = a;
    }
}

#[link(name = "extlib")]
extern {
   fn register_callback(target: *mut RustObject,
                        cb: extern fn(*mut RustObject, i32)) -> i32;
   fn trigger_callback();
}

fn main() {
    // 创建一个会被在回调函数中引用的 RustObject
    let mut rust_object = Box::new(RustObject { a: 5 });

    unsafe {
        register_callback(&mut *rust_object, callback);
        trigger_callback();
    }
}
```

C 代码：

```c
typedef void (*rust_callback)(void*, int32_t);
void* cb_target;
rust_callback cb;

int32_t register_callback(void* callback_target, rust_callback callback) {
    cb_target = callback_target;
    cb = callback;
    return 1;
}

void trigger_callback() {
  cb(cb_target, 7); // 这会调用 Rust 代码中的 callback(&rustObject, 7)
}
```

## 异步回调

在之前给出的例子中，回调是作为对外部 C 库的函数调用的同步调用的。为了执行回调，对当前线程的控制从 Rust 切换到 C，再切换到 Rust，但最终回调是在调用触发回调的函数的同一线程上执行。

当外部库生成自己的线程并从那里调用回调时，事情会变得更加复杂。在这种情况下，对回调中的 Rust 数据结构的访问特别不安全，必须使用适当的同步机制。除了像 mutex 这样的经典同步机制，Rust 中的一种可能性是使用通道（在`std::sync::mpsc`中），将数据从调用回调的 C 线程转发到 Rust 线程。

如果一个异步回调的目标是 Rust 地址空间中的一个特殊对象，那么在相应的 Rust 对象被销毁后，C 库也绝对不能再进行回调。这可以通过在对象的析构器中取消对回调的注册来实现，并以保证在取消注册后不执行回调的方式设计库。

## 链接

`extern`块上的`link`属性提供了基本的构建模块，用于指示 rustc 如何链接到本地库。现在有两种可接受的 link 属性的形式：

- `#[link(name = "foo")]`
- `#[link(name = "foo", kind = "bar")]`

在这两种情况下，`foo`是我们要链接的本地库的名称，在第二种情况下，`bar`是编译器要链接的本地库的类型。目前已知有三种类型的本地库：

- 动态 - `#[link(name = "readline")]`
- 静态 - `#[link(name = "my_build_dependency", kind = "static")]`
- 框架 - `#[link(name = "CoreFoundation", kind = "framework")]`

注意，框架只在 macOS 上可用。

不同的`kind`值是为了区分本地库如何参与链接。从链接的角度来看，Rust 编译器创建了两种类型的工件：部分（rlib/staticlib）和最终（dylib/binary）。原生的动态库和框架依赖被传播到最终的可执行文件中，而静态库的依赖则完全不被传播，因为静态库被直接集成到后续的可执行文件中的。

来看几个这个模型如何使用的例子：

- 一个本地构建依赖。有时在编写一些 Rust 代码时需要一些 C/C++ 胶水，但以库的形式分发 C/C++ 代码是一种负担。在这种情况下，代码将被归档到`libfoo.a`，然后 Rust crate 将通过`#[link(name = "foo", kind = "static")]`声明一个依赖关系。

  无论 crate 的输出是什么，本地静态库都会被包含在输出中，这意味着本地静态库的分发是没有必要的。

- 一个正常的动态依赖。常见的系统库（如`readline`）在大量的系统上可用，而这些库的静态副本往往找不到。当这种依赖被包含在 Rust crate 中时，部分目标（如 rlibs）将不会链接到该库，但当 rlib 被包含在最终目标（如二进制）中时，本地库将被链接进来。

在 macOS 上，框架的行为与动态库的语义相同。

## 不安全块

一些操作，如取消引用原始指针或调用被标记为不安全的函数，只允许在不安全块中进行。不安全块隔离了不安全因素，并向编译器承诺不安全因素不会从块中泄露出去。

另一方面，不安全的函数则向世界公布了它。一个不安全的函数是这样写的：

```rust
unsafe fn kaboom(ptr: *const i32) -> i32 { *ptr }
```

这个函数只能从一个“不安全”块或另一个“不安全”函数中调用。

## 访问外部的全局变量

外部的 API 经常输出一个全局变量，它可以做一些类似于跟踪全局状态的事情。为了访问这些变量，你可以在`extern`块中用`static`关键字来声明它们：

<!-- ignore: requires libc crate -->

```rust,ignore
#[link(name = "readline")]
extern {
    static rl_readline_version: libc::c_int;
}

fn main() {
    println!("You have readline version {} installed.",
             unsafe { rl_readline_version as i32 });
}
```

另外，你可能需要改变由外部接口提供的全局状态。要做到这一点，可以用`mut`声明全局变量，这样我们就可以改变它们：

<!-- ignore: requires libc crate -->

```rust,ignore
use std::ffi::CString;
use std::ptr;

#[link(name = "readline")]
extern {
    static mut rl_prompt: *const libc::c_char;
}

fn main() {
    let prompt = CString::new("[my-awesome-shell] $").unwrap();
    unsafe {
        rl_prompt = prompt.as_ptr();

        println!("{:?}", rl_prompt);

        rl_prompt = ptr::null();
    }
}
```

注意，所有“可变全局变量”的交互都是不安全的，包括读和写。处理全局可变状态需要非常小心。

## 外部调用规约

大多数外部代码都暴露了一个 C ABI，Rust 在调用外部函数时默认使用平台的 C 调用约定。一些外部函数，最明显的是 Windows API，使用了其他的调用约定。Rust 提供了一种方法来告诉编译器应该使用哪种约定：

<!-- ignore: requires libc crate -->

```rust,ignore
#[cfg(all(target_os = "win32", target_arch = "x86"))]
#[link(name = "kernel32")]
#[allow(non_snake_case)]
extern "stdcall" {
    fn SetEnvironmentVariableA(n: *const u8, v: *const u8) -> libc::c_int;
}
# fn main() { }
```

这适用于整个`extern`块。支持的 ABI 约束列表如下：

- `stdcall`
- `aapcs`
- `cdecl`
- `fastcall`
- `thiscall`
- `vectorcall` 这是目前隐藏在`abi_vectorcall`特性开关后面的，可能会有变化
- `Rust`
- `rust-intrinsic`
- `system`
- `C`
- `win64`
- `sysv64`

这个列表中的大多数 ABI 是不言自明的，但是`system` ABI 可能看起来有点奇怪。这个约束条件选择了任何合适的 ABI 来与目标库进行交互操作。例如，在 x86 架构的 win32 上，这意味着使用的 ABI 是`stdcall`。然而，在 x86_64 上，windows 使用`C`调用惯例，所以将使用`C`。这意味着在我们之前的例子中，我们可以使用`extern "system" { ... }`来为所有的 windows 系统定义一个块，而不仅仅是 x86 系统。

## 与外部代码的互操作性

只有当`#[repr(C)]`属性应用于一个`struct`时，Rust 才能保证该结构的布局与平台的 C 语言表示兼容。`#[repr(C, packed)]`可以用来布局结构成员而不需要填充。`#[repr(C)]`也可以应用于枚举。

Rust 的 Box 类型（`Box<T>`）使用不可为空的指针作为句柄，指向所包含的对象。然而，它们不应该被手动创建，因为它们是由内部分配器管理的。引用可以安全地被认为是直接指向该类型的不可归零的指针。然而，打破借用检查或可变性规则是不安全的，所以如果需要的话，最好使用原始指针（`*`），因为编译器不能对它们做出那么多假设。

向量和字符串共享相同的基本内存布局，并且在`vec`和`str`模块中提供了与 C API 工作的实用程序。然而，字符串不是以`\0`结束的。如果你需要一个以 NUL 结尾的字符串与 C 语言互通，你应该使用`std::ffi`模块中的`CString`类型。

crates.io 上的[`libc` crate][libc]包括`libc`模块中的 C 标准库的类型别名和函数定义，Rust 默认与`libc`和`libm`链接。

## Variadic 函数

在 C 语言中，函数可以是“variadic”，这意味着它们接受可变数量的参数。这在 Rust 中可以通过在外部函数声明的参数列表中指定“...”来实现：

```no_run
extern {
    fn foo(x: i32, ...);
}

fn main() {
    unsafe {
        foo(10, 20, 30, 40, 50);
    }
}
```

正常的 Rust 函数*不能*是可变参数的：

```rust,compile_fail
// 这不会编译通过

fn foo(x: i32, ...) {}
```

## "空指针优化"

某些 Rust 类型被定义为永不为“空”。这包括引用（`&T`, `&mut T`）, Box（`Box<T>`）, 和函数指针（`extern "abi" fn()`）。当与 C 语言对接时，经常使用可能为“空”的指针，这似乎需要一些混乱的`transmute`和/或不安全的代码来处理与 Rust 类型的转换。然而，尝试构造或者使用这些无效的值**是 undefined behavior**，所以你应当使用如下的变通方法。

作为一种特殊情况，如果一个“enum”正好包含两个变体，其中一个不包含数据，另一个包含上面列出的非空类型的字段，那么它就有资格获得“空指针优化”。这意味着不需要额外的空间来进行判别；相反，空的变体是通过将一个`null`的值放入不可空的字段来表示。这被称为“优化”，但与其他优化不同，它保证适用于符合条件的类型。

最常见的利用空指针优化的类型是`Option<T>`，其中`None`对应于`null`。所以`Option<extern "C" fn(c_int) -> c_int>`是使用 C ABI（对应于 C 类型`int (*)(int)`）来表示可空函数指针的一种正确方式。

这里有一个臆造的例子：假设某个 C 库有一个用于注册回调的工具，在某些情况下会被调用。回调被传递给一个函数指针和一个整数，它应该以整数为参数运行该函数。所以我们有函数指针在 FFI 边界上双向飞行。

<!-- ignore: requires libc crate -->

```rust,ignore
use libc::c_int;

# #[cfg(hidden)]
extern "C" {
    /// 注册回调函数
    fn register(cb: Option<extern "C" fn(Option<extern "C" fn(c_int) -> c_int>, c_int) -> c_int>);
}
# unsafe fn register(_: Option<extern "C" fn(Option<extern "C" fn(c_int) -> c_int>,
#                                            c_int) -> c_int>)
# {}

// 这个函数其实没什么实际的用处，
// 它从C代码接受一个函数指针和一个整数，
// 用整数做参数，调用指针指向的函数，并返回函数的返回值，
// 如果没有指定函数，那默认就返回整数的平方
extern "C" fn apply(process: Option<extern "C" fn(c_int) -> c_int>, int: c_int) -> c_int {
    match process {
        Some(f) => f(int),
        None    => int * int
    }
}

fn main() {
    unsafe {
        register(Some(apply));
    }
}
```

而 C 语言方面的代码看起来是这样的：

```c
void register(int (*f)(int (*)(int), int)) {
    ...
}
```

实际上，不需要`transmute`!

## FFI 和 panic

在使用 FFI 时，必须注意`panic!`。一个跨越 FFI 边界的“panic!”是未定义的行为。如果你写的代码可能会出现恐慌，你应该用[`catch_unwind`]在闭包中运行它。

```rust
use std::panic::catch_unwind;

#[no_mangle]
pub extern fn oh_no() -> i32 {
    let result = catch_unwind(|| {
        panic!("Oops!");
    });
    match result {
        Ok(_) => 0,
        Err(_) => 1,
    }
}

fn main() {}
```

请注意，[`catch_unwind`]只捕捉 unwind 的 panic，而不是那些中止进程的恐慌。更多信息请参见[`catch_unwind`]的文档。

[`catch_unwind`]: https://doc.rust-lang.org/std/panic/fn.catch_unwind.html

## 表示不透明（opaque）的结构

有时，一个 C 语言库想提供一个指向某东西的指针，但又不想让你知道它想要的东西的内部细节。一个稳定而简单的方法是使用一个`void *`参数。

```c
void foo(void *arg);
void bar(void *arg);
```

我们可以在 Rust 中用`c_void`类型来表示。

<!-- ignore: requires libc crate -->

```rust,ignore
extern "C" {
    pub fn foo(arg: *mut libc::c_void);
    pub fn bar(arg: *mut libc::c_void);
}
# fn main() {}
```

这是一种完全有效的处理方式。然而，我们可以做得更好一点。为了解决这个问题，一些 C 库会创建一个`struct`，其中结构的细节和内存布局是私有的，这提供了某种程度的类型安全。这些结构被称为“不透明的”。下面是一个例子，在 C 语言中：

```c
struct Foo; /* Foo 是一个接口，但它的内容不属于公共接口 */
struct Bar;
void foo(struct Foo *arg);
void bar(struct Bar *arg);
```

为了在 Rust 中做到这一点，让我们创建我们自己的不透明类型：

```rust
#[repr(C)]
pub struct Foo {
    _data: [u8; 0],
    _marker:
        core::marker::PhantomData<(*mut u8, core::marker::PhantomPinned)>,
}
#[repr(C)]
pub struct Bar {
    _data: [u8; 0],
    _marker:
        core::marker::PhantomData<(*mut u8, core::marker::PhantomPinned)>,
}

extern "C" {
    pub fn foo(arg: *mut Foo);
    pub fn bar(arg: *mut Bar);
}
# fn main() {}
```

通过包括至少一个私有字段和没有构造函数，我们创建了一个不透明的类型，我们不能在这个模块之外实例化（否则，一个没有字段的结构可以被任何人实例化）。我们也想在 FFI 中使用这个类型，所以我们必须添加`#[repr(C)]`。该标记确保编译器不会将该结构标记为`Send`、`Sync`，并且`Unpin`也不会应用于该结构（`*mut u8`不是`Send`或者`Sync`，`PhantomPinned`也不是`Unpin`）。

但是因为我们的`Foo`和`Bar`类型不同，我们将在它们两个之间获得类型安全，所以我们不能意外地将`Foo`的指针传递给`bar()`。

注意，使用空枚举作为 FFI 类型是一个非常糟糕的主意。编译器假设空枚举是无法使用的，所以处理`&Empty`类型的值会是意料之外的，并可能导致错误的程序行为（通过触发未定义行为）。

> **注意：** 最简单的方法还是使用“extern 类型”。但它目前（截至 2021 年 10 月）还不稳定，而且还有一些未解决的问题，更多细节请参见[RFC 页面][extern-type-rfc]和[跟踪 Issue][extern-type-issue]。

[extern-type-issue]: https://github.com/rust-lang/rust/issues/43467
[extern-type-rfc]: https://rust-lang.github.io/rfcs/1861-extern-types.html
