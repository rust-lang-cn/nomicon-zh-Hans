# 所有权和生命周期

所有权是 Rust 的突破性功能。它使 Rust 能够做到完全的内存安全和高效，同时避免了垃圾回收。在详细介绍所有权系统之前，我们将考虑这一设计的动机。

我们将假设你接受垃圾收集（GC）并不总是一个最佳解决方案，而且在某些情况下手动管理内存是可取的。如果你不接受这一点，我是否可以让你对另一种语言感兴趣？

不管你对 GC 的看法如何，它显然是一个使代码更安全的*好办法*，你永远不必担心你的对象会在引用失效前就被释放。这是一个 C 和 C++ 程序需要处理的普遍存在的问题。比如下面这个简单的错误，我们所有使用过非 GC 语言的人都曾经犯过：

```rust,compile_fail
fn as_str(data: &u32) -> &str {
    // compute the string
    let s = format!("{}", data);

    // OH NO! We returned a reference to something that
    // exists only in this function!
    // Dangling pointer! Use after free! Alas!
    // (this does not compile in Rust)
    &s
}
```

这正是 Rust 的所有权系统所要解决的问题。Rust 知道`&s`所在的范围，因此可以防止它逃逸。然而，这是一个简单的案例，即使是 C 语言的编译器也能合理地抓住。随着代码越来越大，指针被送入各种函数，事情变得越来越复杂。最终，C 语言编译器会倒下，无法进行足够的转义分析来证明你的代码不健全。因此，它将被迫接受你的程序，假设它是正确的。

这种情况永远不会发生在 Rust 上，Rust 要求程序员来向编译器证明一切是正确的。

当然，Rust 围绕所有权的故事要比仅仅验证引用不脱离其所有者的范围要复杂得多，这是因为确保指针始终有效要比这复杂得多。例如，在这段代码中：

```rust,compile_fail
let mut data = vec![1, 2, 3];
// get an internal reference
let x = &data[0];

// OH NO! `push` causes the backing storage of `data` to be reallocated.
// Dangling pointer! Use after free! Alas!
// (this does not compile in Rust)
data.push(4);

println!("{}", x);
```

简单的作用域分析不足以防止这个 bug，因为`data`事实上确实存活得足够久，满足我们的需求。然而，当我们对它有一个引用时，它被*改变*了。这就是为什么 Rust 要求任何引用都要冻结引用者和其所有者。
