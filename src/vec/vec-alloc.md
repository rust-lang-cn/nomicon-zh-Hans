# 分配内存

使用`NonNull`会给 Vec（甚至是所有的 std collections）的一个重要特性带来麻烦：创建一个空的 Vec 实际上根本就没有分配。这与分配一个零大小的内存块不同，因为全局分配器不允许这样做（会导致未定义行为！）。所以，如果我们不能分配，但也不能在`ptr`里放一个空指针，我们在`Vec::new`里做什么？好吧，我们只是在里面放一些其他的垃圾值。

这并不会有问题，因为我们已经有了`cap == 0`作为尚未分配的哨兵。我们甚至不需要在任何代码中特别处理它，因为我们通常需要检查`cap > len`或`len > 0`。在这里，Rust 推荐使用的值是`mem::align_of::<T>()`。`NonNull`为此提供了一个便利。`NonNull::dangling()`。有相当多的地方我们会想使用`dangling`，因为没有真正的分配可言，但`null`会让编译器做坏事。

所以，代码如下：

<!-- ignore: explanation code -->
```rust,ignore
use std::mem;

impl<T> Vec<T> {
    fn new() -> Self {
        assert!(mem::size_of::<T>() != 0, "We're not ready to handle ZSTs");
        Vec {
            ptr: NonNull::dangling(),
            len: 0,
            cap: 0,
            _marker: PhantomData,
        }
    }
}
# fn main() {}
```

我在这里使用了断言，是因为零大小的类型需要在我们的代码中进行一些特殊的处理，我想把这个问题暂时延后。如果没有这个断言，我们早期的一些实现会导致一些非常糟糕的事情。

接下来，我们需要弄清楚，当我们*确实*想要分配内存时，究竟该怎么做。为此，我们使用全局分配函数[`alloc`][alloc]、[`realloc`][realloc]和[`dealloc`][dealloc]，这些函数在稳定的 Rust 中可以使用[`std::alloc`][std_alloc]。在[`std::alloc::Global`][Global]类型稳定后，这些函数将被废弃。

我们还需要一种方法来处理内存不足（OOM）的情况。标准库提供了一个函数[`alloc::handle_alloc_error`][handle_alloc_error]，它将以特定平台的方式中止程序。我们选择中止而不是 panic 的原因是，unwinding 会导致分配的发生，而当你的分配器刚刚回来说“嘿，我没有更多的内存了”时，这似乎是一件坏事。

当然，这看起来有点蠢，因为大多数平台实际上不会以传统方式耗尽内存。如果你顺理成章地用完了所有的内存，你的操作系统可能会通过其他方式杀死这个应用程序。我们最有可能触发 OOM 的方式是一次性要求大量的内存（例如，理论地址空间的一半）。因此，panic *可能*是没问题的，不会发生什么坏事。不过，我们还是想尽可能地像标准库一样，所以我们就把整个程序杀掉。

好了，现在我们可以写 grow 的代码了，简单来说，逻辑应该是这样的：

```text
if cap == 0:
    allocate()
    cap = 1
else:
    reallocate()
    cap *= 2
```

但是 Rust 唯一支持的分配器 API 太低级了，我们需要做相当多的额外工作。我们还需要防范一些特殊情况，这些情况可能发生在真正的大分配或空分配中。

特别是，`ptr::offset`会给我们带来很多麻烦，因为它有 LLVM 的 GEP（译者注：[GetElementPtr](https://llvm.org/docs/LangRef.html#getelementptr-instruction)） inbounds 指令的语义。如果你有幸没有处理过这个指令，这里是 GEP 的大致故事：别名分析、别名分析、别名分析！对于一个优化的编译器来说，能够推理出数据的依赖性和别名是超级重要的。

作为一个简单的例子，考虑下面的代码片段：

<!-- ignore: simplified code -->
```rust,ignore
*x *= 7;
*y *= 3;
```

如果编译器能够证明`x`和`y`指向内存中的不同位置，理论上这两个操作可以并行执行（例如将它们加载到不同的寄存器中，并对它们独立工作）。然而，编译器在一般情况下不能这样做，因为如果 x 和 y 指向内存中的同一位置，操作需要对相同的值进行，而且它们不能在事后被合并。

当你使用 GEP inbounds 时，你就是在明确地告诉 LLVM，你要做的偏移是在一个“已分配”对象的范围内（within the bounds of a single "allocated" entity.）。这达到的效果是，LLVM 可以假设，如果两个指针已知指向两个不相干的对象，那么这些指针的所有偏移量*也*被认为不会导致别名（因为你不会在内存中的某个随机地方结束）。LLVM 对 GEP 的偏移量进行了大量的优化，而界内偏移量（inbounds offsets）是所有偏移量中最好的，所以我们尽可能地使用它们是很重要的。

这是 GEP 的作用，它怎么会给我们带来麻烦呢？

第一个问题是，我们用无符号的整数来索引数组，但是 GEP（以及由此产生的`ptr::offset`）需要一个有符号的整数。这意味着一半的看似有效的数组索引会溢出 GEP，并且在实际上是走错了方向！因此，我们必须将所有的分配限制在`isize::MAX`元素。这实际上意味着我们只需要担心字节大小的对象，因为例如`> isize::MAX``u16`s将真正耗尽系统的所有内存。然而，为了避免出现微妙的边界情况，即有人将一些`< isize::MAX`对象的数组重新解释为字节，std 将所有分配限制为`isize::MAX`字节。

在 Rust 目前支持的所有 64 位平台上，我们被人为地限制在明显少于所有 64 位的地址空间（现代 x64 平台只暴露了 48 位寻址），所以我们可以依靠首先耗尽内存。然而，在 32 位目标上，特别是那些有扩展使用更多地址空间的目标（PAE x86 或 x32），理论上是可以成功分配超过`isize::MAX`字节的内存的。

然而，由于这是一个教程，我们在这里不会特别优化，只是无条件地检查，而不是使用聪明的平台特定的`cfg`s。

我们需要担心的另一个情况是空分配。我们需要担心两种空分配的情况。对于任意 T：`cap = 0`；和对于零大小的类型（zero-sized types）`cap > 0`。

这些情况很棘手，因为它们归结于 LLVM 对“分配”的理解。LLVM 的分配概念要比我们通常使用的方式抽象得多。因为 LLVM 需要与不同语言的语义和自定义分配器一起工作，所以它不能真正深入地理解分配。相反，分配背后的主要想法是“不与其他东西重叠”。也就是说，堆分配、栈分配和 globals 不会随机地重叠在一起。没错，这就是别名分析。因此，Rust 在技术上可以对分配的概念做一些快速和松散的处理，只要它是*一致的*。

回到空分配的情况，有几个地方我们想用 0 来抵消，这是通用代码的结果。那么问题来了：这样做是否一致？对于零大小的类型，我们的结论是，用任意数量的元素进行 GEP 界内偏移确实是一致的。这是一个运行时的无用功，因为每个元素都不占用空间，假装在`0x01`处有无限的零尺寸类型分配也是可以的。没有分配器会分配这个地址，因为他们不会分配`0x00`，而且他们一般会分配到高于一个字节的最小对齐。另外，一般来说，整个第一页的内存是被保护的，不会被分配（在许多平台上，是整个4k）。

然而，对于正值大小的类型怎么办呢？这个问题就有点棘手了。原则上，你可以说 0 的偏移量没有给 LLVM 带来任何信息：要么地址之前有一个元素，要么在它之后，但它不能知道是哪个。然而，我们选择了保守的假设，即它可能会做坏事。因此，我们将明确地防止这种情况。

*呼*。

好了，说了这么多废话，让我们实际分配一些内存吧：

<!-- ignore: simplified code -->
```rust,ignore
use std::alloc::{self, Layout};

impl<T> Vec<T> {
    fn grow(&mut self) {
        let (new_cap, new_layout) = if self.cap == 0 {
            (1, Layout::array::<T>(1).unwrap())
        } else {
            // 因为 self.cap <= isize::MAX，所以不会溢出
            let new_cap = 2 * self.cap;

            // `Layout::array` 会检查申请的空间是否满足 <= usize::MAX,
            // 但是因为 old_layout.size() <= isize::MAX,
            // 所以这里的 unwrap 永远不可能失败
            let new_layout = Layout::array::<T>(new_cap).unwrap();
            (new_cap, new_layout)
        };

        // 保证新申请的内存没有超出`isize::MAX`字节的大小.
        assert!(new_layout.size() <= isize::MAX as usize, "Allocation too large");

        let new_ptr = if self.cap == 0 {
            unsafe { alloc::alloc(new_layout) }
        } else {
            let old_layout = Layout::array::<T>(self.cap).unwrap();
            let old_ptr = self.ptr.as_ptr() as *mut u8;
            unsafe { alloc::realloc(old_ptr, old_layout, new_layout.size()) }
        };

        // 如果分配失败，`new_ptr` 就会称为空指针，我们需要对应abort的操作
        self.ptr = match NonNull::new(new_ptr as *mut T) {
            Some(p) => p,
            None => alloc::handle_alloc_error(new_layout),
        };
        self.cap = new_cap;
    }
}
# fn main() {}
```

[Global]: https://doc.rust-lang.org/std/alloc/struct.Global.html
[handle_alloc_error]: https://doc.rust-lang.org/alloc/alloc/fn.handle_alloc_error.html
[alloc]: https://doc.rust-lang.org/alloc/alloc/fn.alloc.html
[realloc]: https://doc.rust-lang.org/alloc/alloc/fn.realloc.html
[dealloc]: https://doc.rust-lang.org/alloc/alloc/fn.dealloc.html
[std_alloc]: https://doc.rust-lang.org/alloc/alloc/index.html
