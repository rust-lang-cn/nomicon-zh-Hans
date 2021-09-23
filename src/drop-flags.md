# 丢弃标志

上一节的例子为 Rust 引入了一个有趣的问题。我们已经看到，可以完全安全地对内存位置进行有条件的初始化、非初始化和重新初始化。对于实现了`Copy`的类型来说，这并不特别值得注意，因为它们只是一堆随机的比特。然而，带有析构器的类型是一个不同的故事。Rust 需要知道每当一个变量被赋值，或者一个变量超出范围时，是否要调用一个析构器。它怎么能用条件初始化来做到这一点呢？

请注意，这不是所有赋值都需要担心的问题。特别是，通过解引用的赋值会无条件地被丢弃，而相对的，在`let`中的赋值无论如何都不会被丢弃：

```rust
let mut x = Box::new(0); // let makes a fresh variable, so never need to drop
let y = &mut x;
*y = Box::new(1); // Deref assumes the referent is initialized, so always drops
```

仅当覆盖先前初始化的变量或其子字段之一时，这才是个问题。

这种情况下，Rust 实际上是在*运行时*跟踪一个类型是否应该被丢弃。当一个变量被初始化和未初始化时，该变量的*drop flag*被切换。当一个变量可能需要被丢弃时，这个标志会被读取，以确定它是否应该被丢弃。

当然，通常的情况是，一个值的初始化状态在程序的每一个点上都是静态已知的。如果是这种情况，那么编译器理论上可以生成更有效的代码。例如，直线型代码就有这样的*静态丢弃语义（static drop semantics）*：

```rust
let mut x = Box::new(0); // x was uninit; just overwrite.
let mut y = x;           // y was uninit; just overwrite and make x uninit.
x = Box::new(0);         // x was uninit; just overwrite.
y = x;                   // y was init; Drop y, overwrite it, and make x uninit!
                         // y goes out of scope; y was init; Drop y!
                         // x goes out of scope; x was uninit; do nothing.
```

类似地，所有分支都在初始化方面具有相同行为的代码具有静态丢弃语义：

```rust
# let condition = true;
let mut x = Box::new(0);    // x was uninit; just overwrite.
if condition {
    drop(x)                 // x gets moved out; make x uninit.
} else {
    println!("{}", x);
    drop(x)                 // x gets moved out; make x uninit.
}
x = Box::new(0);            // x was uninit; just overwrite.
                            // x goes out of scope; x was init; Drop x!
```

然而像这样的代码*需要*运行时的信息来正确地 Drop：

```rust
# let condition = true;
let x;
if condition {
    x = Box::new(0);        // x was uninit; just overwrite.
    println!("{}", x);
}
                            // x goes out of scope; x might be uninit;
                            // check the flag!
```

当然，在这种情况下，获得静态丢弃语义是很简单的：

```rust
# let condition = true;
if condition {
    let x = Box::new(0);
    println!("{}", x);
}
```

丢弃标志在栈中被跟踪，而不再藏在实现`Drop`的类型中。
