# 未经检查的未初始化的内存

这个规则的一个有趣的例外是与数组一起工作。Safe Rust 不允许你部分初始化一个数组。当你初始化一个数组时，你可以用`let x = [val; N]`将每个值设置为相同的东西，或者你可以用 `let x = [val1, val2, val3]`单独指定每个成员。不幸的是，这是很死板的，特别是当你需要以更多的增量或动态方式初始化你的数组时。

不安全的 Rust 给了我们一个强大的工具来处理这个问题：[`MaybeUninit`]。这个类型可以用来处理还没有完全初始化的内存。

使用`MaybeUninit`，我们可以对一个数组进行逐个元素的初始化，如下所示：

```rust
use std::mem::{self, MaybeUninit};

// 数组的大小是硬编码的，可以很方便地修改（改变几个硬编码的常数非常容易）
// 这表示我们不能用 [a, b, c] 这种方式初始化数组，因为我们必须要和硬编码中的 `SIZE` 保持同步！
const SIZE: usize = 10;

let x = {
    // 创建一个未初始化，类型为 `MaybeUninit` 的数组，
    // 因为这里声明的是一堆 `MaybeUninit`，不要求初始化，所以 `assume_init` 操作是安全的
    let mut x: [MaybeUninit<Box<u32>>; SIZE] = unsafe {
        MaybeUninit::uninit().assume_init()
    };

    // 因为 drop 一个 `MaybeUninit` 什么都不做，
    // 所以使用直接的裸指针赋值（而非 ptr::write）不会导致原先未初始化的变量被 drop
    // 不需要在这里考虑异常安全，因为 Box 永远不会 panic
    for i in 0..SIZE {
        x[i] = MaybeUninit::new(Box::new(i as u32));
    }

    // 一切都初始化完毕，将未初始化的类型强制转换为初始化的类型
    unsafe { mem::transmute::<_, [Box<u32>; SIZE]>(x) }
};

dbg!(x);
```

这段代码分三步进行：

1. 创建一个`MaybeUninit<T>`的数组。在当前稳定版的 Rust 中，我们必须使用不安全的代码来实现：我们取一些未初始化的内存（`MaybeUninit::uninit()`），并声称我们已经完全初始化了它（[`assume_init()`][assumed_init]）。这似乎很荒谬，因为我们没有！这是正确的，因为数组本身完全由`MaybeUninit`组成，实际上不需要初始化。对于大多数其他类型，`MaybeUninit::uninit().assume_init()`会产生一个无效的类型实例，所以你荣获了一些未定义行为。

2. 初始化数组。这个问题的微妙之处在于，通常情况下，当我们使用`=`赋值给一个 Rust 类型检查器认为已经初始化的值时（比如`x[i]`），存储在左边的旧值会被丢掉。这将是一场灾难。然而，在这种情况下，左边的类型是`MaybeUninit<Box<u32>>`，丢弃这个类型什么都不会发生，关于这个`drop`问题的更多讨论，见下文。

3. 最后，我们必须改变我们数组的类型，以去除`MaybeUninit`。在当前稳定的 Rust 中，这需要一个`transmute`。这种转换是合法的，因为在内存中，`MaybeUninit<T>`看起来和`T`一样。

    然而，请注意，在一般情况下，`Container<MaybeUninit<T>>`与`Container<T>`看起来*并不*一样! 假如`Container`是`Option`，而`T`是`bool`，那么`Option<bool>`就利用了`bool`只有两个有效值，但`Option<MaybeUninit<bool>>`不能这样做，因为`bool`不需要被初始化。

    所以，这取决于`Container`是否允许将`MaybeUninit`转化掉。对于数组来说，它是允许的（最终标准库会通过提供适当的方法来达到这一点）。

让我们在中间的循环上多花一点时间，特别是赋值运算符和它与`drop`的交互。比如这样的代码：

<!-- ignore: simplified code -->
```rust,ignore
*x[i].as_mut_ptr() = Box::new(i as u32); // 错误！
```

我们实际上会覆盖一个`Box<u32>`，导致在未初始化数据上调用`drop`，这将给你带来很多乐子。

如果由于某种原因我们不能使用`MaybeUninit::new`，正确的选择是使用[`ptr`]模块。特别是，它提供了三个函数，允许我们将字节分配到内存中的某个位置而不丢弃旧值。[`write`]、[`copy`]和[`copy_nonoverlapping`]。

* `ptr::write(ptr, val)`接收一个`val`并将其移动到`ptr`所指向的地址
* `ptr::copy(src, dest, count)`将`count`个 T 所占用的位从 src 复制到 dest(这等同于 memmove —— 注意参数顺序是相反的！)
* `ptr::copy_nonoverlapping(src, dest, count)`做的是`copy`的工作，但是在假设两个内存范围不重叠的情况下，速度更快(这等同于 memcpy —— 注意参数顺序是相反的！)

自然不用说，这些函数如果被误用，会造成严重的破坏，或者直接导致未定义行为。这些函数*本身*需要的唯一东西是，你想读和写的位置已经被分配并正确对齐。然而，向内存的任意位置写入任意位的方式所带来的问题是无穷无尽的。

值得注意的是，你不需要担心在未实现`Drop`或者不包含`Drop`类型的类型上使用`ptr::write`带来的问题，因为 Rust 知道这个信息，并且不会调用`drop`。这也是我们在上面的例子中所依赖的。

然而，当你处理未初始化的内存时，你需要时刻警惕 Rust 试图在它们完全初始化之前丢弃你创建的这些值。如果它有一个析构器的话，该变量作用域内的每个控制路径必须在结束前初始化该值。*[这包括 panic]（unwinding.html）*。`MaybeUninit`在这方面有一点用，因为它不会隐式地丢弃它的内容——但在 panic 的情况下，这实际上意味着不是对尚未初始化的部分进行双重释放，而是对已经初始化的部分导致了内存泄漏。

注意，为了使用`ptr`方法，你需要首先获得一个你想初始化的数据的*raw pointer*。对未初始化的数据构建一个*引用*是非法的，这意味着你在获得上述原始指针时必须小心：

* 对于一个`T`的数组，你可以使用`base_ptr.add(idx)`，其中`base_ptr: *mut T`来计算数组索引`idx`的地址。这依赖于数组在内存中的布局方式
* 然而，对于一个结构体，一般来说，我们不知道它是如何布局的，而且我们也不能使用`&mut base_ptr.field`，因为这将创建一个引用。因此，当你使用[`addr_of_mut`]宏的时候，你必须非常小心，这将跳过中间层直接创建一个指向该字段的裸指针：

```rust
use std::{ptr, mem::MaybeUninit};
struct Demo {
    field: bool,
}
let mut uninit = MaybeUninit::<Demo>::uninit();
// `&uninit.as_mut().field`将会创建一个指向未初始化的`bool`的指针，而这是 UB 行为。
let f1_ptr = unsafe { ptr::addr_of_mut!((*uninit.as_mut_ptr()).field) };
unsafe { f1_ptr.write(true); }
let init = unsafe { uninit.assume_init() };
```
d
最后一句话：在阅读旧的 Rust 代码时，你可能会无意中发现被废弃的`mem::uninitialized`函数。这个函数曾经是处理栈上未初始化内存的唯一方法，但它被证明不能与语言的其他部分很好地结合在一起。在新的代码中你总是应该使用`MaybeUninit`来代替，并且当你有机会的时候，可以把旧的代码移植过来。

这就是与未初始化内存打交道的方法。基本上没有任何地方希望得到未初始化的内存，所以如果你要传递它，一定要*非常*小心。

[`MaybeUninit`]: https://doc.rust-lang.org/core/mem/union.MaybeUninit.html
[assume_init]: https://doc.rust-lang.org/core/mem/union.MaybeUninit.html#method.assume_init
[`ptr`]: https://doc.rust-lang.org/core/ptr/index.html
[`addr_of_mut`]: https://doc.rust-lang.org/core/ptr/macro.addr_of_mut.html
[`write`]: https://doc.rust-lang.org/core/ptr/fn.write.html
[`copy`]: https://doc.rust-lang.org/std/ptr/fn.copy.html
[`copy_nonoverlapping`]: https://doc.rust-lang.org/std/ptr/fn.copy_nonoverlapping.html
