# 经检查的未初始化的内存

和 C 语言一样，Rust 中的所有堆栈变量都是未初始化的，直到为它们明确赋值。与 C 不同的是，Rust 静态地阻止你读取它们，直到你为它们赋值。

```rust,compile_fail
fn main() {
    let x: i32;
    println!("{}", x);
}
```

```text
  |
3 |     println!("{}", x);
  |                    ^ use of possibly uninitialized `x`
```

这基于一个基本的分支分析：每个分支都必须在第一次使用`x`之前给它赋值。有趣的是，如果每个分支恰好赋值一次，Rust 不要求变量是可变的，以执行延迟初始化。然而这个分析并没有利用常量分析或类似的东西。所以下述的代码是可以编译的：

```rust
fn main() {
    let x: i32;

    if true {
        x = 1;
    } else {
        x = 2;
    }

    println!("{}", x);
}
```

但这个不行：

```rust,compile_fail
fn main() {
    let x: i32;
    if true {
        x = 1;
    }
    println!("{}", x);
}
```

```text
  |
6 |     println!("{}", x);
  |                    ^ use of possibly uninitialized `x`
```

这个又可以了：

```rust
fn main() {
    let x: i32;
    if true {
        x = 1;
        println!("{}", x);
    }
    // Don't care that there are branches where it's not initialized
    // since we don't use the value in those branches
}
```

当然，虽然分析不考虑实际值，但它对依赖关系和控制流有相对复杂的理解。例如，这样是可以编译通过的：

```rust
let x: i32;

loop {
    // Rust doesn't understand that this branch will be taken unconditionally,
    // because it relies on actual values.
    if true {
        // But it does understand that it will only be taken once because
        // we unconditionally break out of it. Therefore `x` doesn't
        // need to be marked as mutable.
        x = 0;
        break;
    }
}
// It also knows that it's impossible to get here without reaching the break.
// And therefore that `x` must be initialized here!
println!("{}", x);
```

If a value is moved out of a variable, that variable becomes logically uninitialized if the type of the value isn't Copy. That is:
如果一个值从一个变量中移出，并且该值的类型不是 Copy，该变量在逻辑上就会变成未初始化。也就是说：

```rust
fn main() {
    let x = 0;
    let y = Box::new(0);
    let z1 = x; // x is still valid because i32 is Copy
    let z2 = y; // y is now logically uninitialized because Box isn't Copy
}
```

然而，在这个例子中重新给`y`赋值需要将`y`标记为可变，这样一个安全的 Rust 程序就可以观察到`y`的值发生了变化：

```rust
fn main() {
    let mut y = Box::new(0);
    let z = y; // y is now logically uninitialized because Box isn't Copy
    y = Box::new(1); // reinitialize y
}
```

否则`y`就像是一个全新的变量。
