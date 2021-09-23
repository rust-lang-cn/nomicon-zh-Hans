# 数据竞争和竞态条件

安全的 Rust 保证没有数据竞争，数据竞争的定义是：

* 两个或多个线程同时访问一个内存位置
* 其中一个或多个线程是写的
* 其中一个或多个是非同步的

数据竞争具有未定义行为，因此在 Safe Rust 中不可能执行。数据竞争主要是通过 Rust 的所有权系统来防止的：不可能别名一个可变引用，所以不可能进行数据竞争。但内部可变性使其更加复杂，这也是我们有 Send 和 Sync Trait 的主要原因（见下文）。

**然而，Rust 并没有（也无法）阻止更广泛的竞态条件。**

这从根本上说是不可能的，而且说实话也是不可取的。你的硬件很糟糕，你的操作系统很糟糕，你电脑上的其他程序也很糟糕，而这一切运行的世界也很糟糕。任何能够真正声称防止*所有*竞态条件的系统，如果不是不正确的话，使用起来也是非常糟糕的。

因此，对于一个安全的 Rust 程序来说，在不正确的同步下出现死锁或做一些无意义的事情是完全“正常”的。很明显，这样的程序有问题，但 Rust 只能帮你到这里。不过，Rust 程序中的竞态条件本身并不能违反内存安全；只有与其他不安全的代码结合在一起，竞态条件才能真正违反内存安全。比如说：

```rust,no_run
use std::thread;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::Arc;

let data = vec![1, 2, 3, 4];
// Arc so that the memory the AtomicUsize is stored in still exists for
// the other thread to increment, even if we completely finish executing
// before it. Rust won't compile the program without it, because of the
// lifetime requirements of thread::spawn!
let idx = Arc::new(AtomicUsize::new(0));
let other_idx = idx.clone();

// `move` captures other_idx by-value, moving it into this thread
thread::spawn(move || {
    // It's ok to mutate idx because this value
    // is an atomic, so it can't cause a Data Race.
    other_idx.fetch_add(10, Ordering::SeqCst);
});

// Index with the value loaded from the atomic. This is safe because we
// read the atomic memory only once, and then pass a copy of that value
// to the Vec's indexing implementation. This indexing will be correctly
// bounds checked, and there's no chance of the value getting changed
// in the middle. However our program may panic if the thread we spawned
// managed to increment before this ran. A race condition because correct
// program execution (panicking is rarely correct) depends on order of
// thread execution.
println!("{}", data[idx.load(Ordering::SeqCst)]);
```

```rust,no_run
use std::thread;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::Arc;

let data = vec![1, 2, 3, 4];

let idx = Arc::new(AtomicUsize::new(0));
let other_idx = idx.clone();

// `move` captures other_idx by-value, moving it into this thread
thread::spawn(move || {
    // It's ok to mutate idx because this value
    // is an atomic, so it can't cause a Data Race.
    other_idx.fetch_add(10, Ordering::SeqCst);
});

if idx.load(Ordering::SeqCst) < data.len() {
    unsafe {
        // Incorrectly loading the idx after we did the bounds check.
        // It could have changed. This is a race condition, *and dangerous*
        // because we decided to do `get_unchecked`, which is `unsafe`.
        println!("{}", data.get_unchecked(idx.load(Ordering::SeqCst)));
    }
}
```
