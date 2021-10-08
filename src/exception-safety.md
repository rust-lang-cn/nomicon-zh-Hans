# 异常安全

尽管程序应该很少使用 unwind，但是有很多代码是*可以* panic 的。如果你 unwrap 一个 None，索引出界，或者除以 0，你的程序就会 panic。在 debug build 中，每一个算术运算如果溢出，都会引起 panic。除非你非常小心并严格控制代码的运行，否则几乎所有的东西都可能 unwind，你需要做好准备。

在更广泛的编程世界中，为 unwind 做好准备通常被称为*异常安全*。在 Rust 中，有两个级别的异常安全需要关注：

* 在不安全的代码中，我们*必须*保证异常安全到不违反内存安全的程度。我们把这称为*最小*的异常安全。
* 在安全代码中，保证异常安全到你的程序能做正确的事情的程度（也就是说，啥都不影响，都恢复了）。我们称其为*最大限度的*异常安全。

正如 Rust 中许多地方的情况一样，不安全的代码必须准备好处理有问题的安全代码，当它涉及到 unwind 时。有可能在某一时刻创建不健壮状态的代码必须注意，panic 不会导致该状态被使用。也就是说，这意味着当这些状态存在时，只有非 panicking 的代码才会被运行；或者你需要做一个防护，在 panic 的情况下清理该状态。这并不一定意味着 panic 所见证的状态是一个完全一致的状态。我们只需要保证它是一个*安全*的状态。

大多数不安全代码都是属于叶子代码（也就是不会再调用其它函数/逻辑），因此相当容易使异常安全化。它控制着所有运行的代码，而且大多数代码都不会发生 panic。然而，不安全代码在重复调用调用者提供的代码时，与未初始化的数组打交道是很常见的。这样的代码需要小心谨慎，并考虑异常安全。

## Vec::push_all

`Vec::push_all`是一个临时性的 hack，可以在没有特例化的情况下，通过一个 slice 来高效地扩展一个 Vec。下面是一个简单的实现：

<!-- ignore: simplified code -->
```rust,ignore
impl<T: Clone> Vec<T> {
    fn push_all(&mut self, to_push: &[T]) {
        self.reserve(to_push.len());
        unsafe {
            // 因为我们刚刚预留了空间，所以这里不会溢出
            self.set_len(self.len() + to_push.len());

            for (i, x) in to_push.iter().enumerate() {
                self.ptr().add(i).write(x.clone());
            }
        }
    }
}
```

我们绕过了`push`，以避免对我们明确知道有容量的 Vec 进行多余的容量和`len`检查。这个逻辑是完全正确的，只是我们的代码有一个微妙的问题：它不是异常安全的！`set_len`、`add`和`write`都没问题；但`clone`是我们忽略的 panic 炸弹。

Clone 完全不受我们的控制，而且完全可以自由地 panic。如果它这样做，我们的函数将提前退出；而因为 Vec 的长度被设置得太大了，如果 Vec 被读取或丢弃，未初始化的内存将被读取！

这种情况下的修复方法相当简单，如果我们想保证我们*已经*复制的值被丢弃，我们可以在每个循环迭代中设置`len`。如果我们只是想保证未初始化的内存不能被观察到，我们可以在循环之后设置`len`。

## BinaryHeap::sift_up

把一个元素扔到堆中，比扩展一个 Vec 要复杂一些。伪代码如下：

```text
bubble_up(heap, index):
    while index != 0 && heap[index] < heap[parent(index)]:
        heap.swap(index, parent(index))
        index = parent(index)
```

将这段代码按字面意思翻译成 Rust 是完全没有问题的，但是有一个坑爹的性能问题：`self`元素被无用地反复交换。因此，我们可以这么做：

```text
bubble_up(heap, index):
    let elem = heap[index]
    while index != 0 && elem < heap[parent(index)]:
        heap[index] = heap[parent(index)]
        index = parent(index)
    heap[index] = elem
```

这段代码确保每个元素尽可能少地被复制（事实上，在一般情况下，elem 有必要被复制两次）。但是它现在暴露了一些异常安全问题! 在任何时候，一个值都存在两个副本。如果我们在这个函数中 panic，就会有东西被重复 drop。不幸的是，我们对执行的代码并没有完全的掌控力——因为比较方法是用户定义的！

与 Vec 不同，这里的修复并不容易。一个可选的方案是将用户定义的代码和不安全的代码分成两个独立的阶段：

```text
bubble_up(heap, index):
    let end_index = index;
    while end_index != 0 && heap[end_index] < heap[parent(end_index)]:
        end_index = parent(end_index)

    let elem = heap[index]
    while index != end_index:
        heap[index] = heap[parent(index)]
        index = parent(index)
    heap[index] = elem
```

如果用户定义的代码炸了，那就没有问题了，因为我们还没有真正接触到堆的状态。一旦我们开始接触堆，我们就只与我们信任的数据和函数打交道，所以不存在 panic 的问题。

也许你对这种设计并不满意，不过我不得不说，这确实是在作弊! 而且我们还得做复杂的堆遍历*两次*! 好吧，让我们咬咬牙，把不可信任的和不安全的代码混在一起。

如果 Rust 像 Java 一样有`try`和`finally`，我们就可以做以下事情：

```text
bubble_up(heap, index):
    let elem = heap[index]
    try:
        while index != 0 && elem < heap[parent(index)]:
            heap[index] = heap[parent(index)]
            index = parent(index)
    finally:
        heap[index] = elem
```

基本的想法很简单：如果比较出现问题，我们就把松散的元素扔到逻辑上未初始化的索引中，然后就直接返回。任何观察堆的人都会看到一个潜在的*不一致*的堆，但至少它不会导致任何双重释放问题。而如果算法正常终止，那么这个操作恰好与我们的结束方式不谋而合。

遗憾的是，Rust 没有这样的结构，所以我们需要推出我们自己的结构。这样做的方法是将算法的状态存储在一个单独的结构中，并为“最终”逻辑设置一个析构函数。无论我们是否 panic，这个析构函数都会在我们之后运行和清理：

<!-- ignore: simplified code -->
```rust,ignore
struct Hole<'a, T: 'a> {
    data: &'a mut [T],
    /// `elt` 从始至终都是 Some
    elt: Option<T>,
    pos: usize,
}

impl<'a, T> Hole<'a, T> {
    fn new(data: &'a mut [T], pos: usize) -> Self {
        unsafe {
            let elt = ptr::read(&data[pos]);
            Hole {
                data: data,
                elt: Some(elt),
                pos: pos,
            }
        }
    }

    fn pos(&self) -> usize { self.pos }

    fn removed(&self) -> &T { self.elt.as_ref().unwrap() }

    unsafe fn get(&self, index: usize) -> &T { &self.data[index] }

    unsafe fn move_to(&mut self, index: usize) {
        let index_ptr: *const _ = &self.data[index];
        let hole_ptr = &mut self.data[self.pos];
        ptr::copy_nonoverlapping(index_ptr, hole_ptr, 1);
        self.pos = index;
    }
}

impl<'a, T> Drop for Hole<'a, T> {
    fn drop(&mut self) {
        // fill the hole again
        unsafe {
            let pos = self.pos;
            ptr::write(&mut self.data[pos], self.elt.take().unwrap());
        }
    }
}

impl<T: Ord> BinaryHeap<T> {
    fn sift_up(&mut self, pos: usize) {
        unsafe {
            // 取出 `pos` 的值，然后创建一个 hole
            let mut hole = Hole::new(&mut self.data, pos);

            while hole.pos() != 0 {
                let parent = parent(hole.pos());
                if hole.removed() <= hole.get(parent) { break }
                hole.move_to(parent);
            }
            // 无论是否 panic，这里的 hole 都会被无条件填充
        }
    }
}
```
