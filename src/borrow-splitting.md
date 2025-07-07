# 拆分 Borrows

在处理复合结构时，可变引用的互斥属性会有很大的限制。借用检查器理解一些基本的东西，但是很容易就会出现问题。它对结构有足够的了解，知道有可能同时借用一个结构中不相干的字段。所以现在这个方法是可行的：

```rust
struct Foo {
    a: i32,
    b: i32,
    c: i32,
}

let mut x = Foo {a: 0, b: 0, c: 0};
let a = &mut x.a;
let b = &mut x.b;
let c = &x.c;
*b += 1;
let c2 = &x.c;
*a += 10;
println!("{} {} {} {}", a, b, c, c2);
```

然而 borrowck 完全不理解数组或 slice，所以这会挂：

```rust,compile_fail
let mut x = [1, 2, 3];
let a = &mut x[0];
let b = &mut x[1];
println!("{} {}", a, b);
```

```text
error[E0499]: cannot borrow `x[..]` as mutable more than once at a time
 --> src/lib.rs:4:18
  |
3 |     let a = &mut x[0];
  |                  ---- first mutable borrow occurs here
4 |     let b = &mut x[1];
  |                  ^^^^ second mutable borrow occurs here
5 |     println!("{} {}", a, b);
6 | }
  | - first borrow ends here

error: aborting due to previous error
```

虽然 borrowck 能理解这个简单的案例是合理的，但对于 borrowck 来说，要理解像树这样的一般容器类型的不连通性显然是没有希望的，尤其是当不同的键*确实*映射到相同的值时。

为了“教导” borrowck 我们正在做的事情是正确的，我们需要使用到不安全的代码。例如，可变 slice 暴露了一个`split_at_mut`函数，它消耗这个 slice 并返回两个可变 slice。一个用于索引左边的所有内容，一个用于右边的所有内容。直观地讲，我们知道这是安全的，因为这些分片不会重叠，因此可以进行别名操作。然而，这个实现需要一些不安全代码：

```rust
# use std::slice::from_raw_parts_mut;
# struct FakeSlice<T>(T);
# impl<T> FakeSlice<T> {
# fn len(&self) -> usize { unimplemented!() }
# fn as_mut_ptr(&mut self) -> *mut T { unimplemented!() }
pub fn split_at_mut(&mut self, mid: usize) -> (&mut [T], &mut [T]) {
    let len = self.len();
    let ptr = self.as_mut_ptr();

    unsafe {
        assert!(mid <= len);

        (from_raw_parts_mut(ptr, mid),
         from_raw_parts_mut(ptr.add(mid), len - mid))
    }
}
# }
```

这实际上是有点微妙的。为了避免对同一个值进行两次`&mut`，我们明确地通过原始指针构造全新的切片。

然而，更微妙的是产生可变引用的迭代器如何工作。迭代器 trait 定义如下：

```rust
trait Iterator {
    type Item;

    fn next(&mut self) -> Option<Self::Item>;
}
```

考虑到这个定义，Self::Item 与`self`*没有*联系。这意味着我们可以连续多次调用`next`，并将所有的结果*并发地*保留下来。这对逐值迭代器来说是非常好的，因为它有这样的语义。这对共享引用来说也很好，因为它们允许对同一事物有任意多的引用（尽管迭代器需要和被共享的事物是一个独立的对象）。

但是可变的引用让这变得一团糟。乍一看，它们似乎与这个 API 完全不兼容，因为它将产生对同一个对象的多个可变引用！

然而它实际上*是*有效的，正是因为迭代器是一次性的对象。IterMut 产生的所有东西最多只能产生一次，所以我们实际上不会产生对同一块数据的多个可变引用。

也许令人惊讶的是，对于许多类型，可变迭代器不需要实现不安全的代码。

例如，这里有一个单向链表：

```rust
# fn main() {}
type Link<T> = Option<Box<Node<T>>>;

struct Node<T> {
    elem: T,
    next: Link<T>,
}

pub struct LinkedList<T> {
    head: Link<T>,
}

pub struct IterMut<'a, T: 'a>(Option<&'a mut Node<T>>);

impl<T> LinkedList<T> {
    fn iter_mut(&mut self) -> IterMut<T> {
        IterMut(self.head.as_mut().map(|node| &mut **node))
    }
}

impl<'a, T> Iterator for IterMut<'a, T> {
    type Item = &'a mut T;

    fn next(&mut self) -> Option<Self::Item> {
        self.0.take().map(|node| {
            self.0 = node.next.as_mut().map(|node| &mut **node);
            &mut node.elem
        })
    }
}
```

下面是一个可变的 slice：

```rust
# fn main() {}
use std::mem;

pub struct IterMut<'a, T: 'a>(&'a mut[T]);

impl<'a, T> Iterator for IterMut<'a, T> {
    type Item = &'a mut T;

    fn next(&mut self) -> Option<Self::Item> {
        let slice = mem::take(&mut self.0);
        if slice.is_empty() { return None; }

        let (l, r) = slice.split_at_mut(1);
        self.0 = r;
        l.get_mut(0)
    }
}

impl<'a, T> DoubleEndedIterator for IterMut<'a, T> {
    fn next_back(&mut self) -> Option<Self::Item> {
        let slice = mem::take(&mut self.0);
        if slice.is_empty() { return None; }

        let new_len = slice.len() - 1;
        let (l, r) = slice.split_at_mut(new_len);
        self.0 = l;
        r.get_mut(0)
    }
}
```

接着是一个二叉树：

```rust
# fn main() {}
use std::collections::VecDeque;

type Link<T> = Option<Box<Node<T>>>;

struct Node<T> {
    elem: T,
    left: Link<T>,
    right: Link<T>,
}

pub struct Tree<T> {
    root: Link<T>,
}

struct NodeIterMut<'a, T: 'a> {
    elem: Option<&'a mut T>,
    left: Option<&'a mut Node<T>>,
    right: Option<&'a mut Node<T>>,
}

enum State<'a, T: 'a> {
    Elem(&'a mut T),
    Node(&'a mut Node<T>),
}

pub struct IterMut<'a, T: 'a>(VecDeque<NodeIterMut<'a, T>>);

impl<T> Tree<T> {
    pub fn iter_mut(&mut self) -> IterMut<T> {
        let mut deque = VecDeque::new();
        if let Some(root) = self.root.as_mut() {
            deque.push_front(root.iter_mut());
        }
        IterMut(deque)
    }
}

impl<T> Node<T> {
    pub fn iter_mut(&mut self) -> NodeIterMut<T> {
        NodeIterMut {
            elem: Some(&mut self.elem),
            left: self.left.as_deref_mut(),
            right: self.right.as_deref_mut(),
        }
    }
}


impl<'a, T> Iterator for NodeIterMut<'a, T> {
    type Item = State<'a, T>;

    fn next(&mut self) -> Option<Self::Item> {
        self.left.take().map(State::Node).or_else(|| {
            self.elem
                .take()
                .map(State::Elem)
                .or_else(|| self.right.take().map(State::Node))
        })
    }
}

impl<'a, T> DoubleEndedIterator for NodeIterMut<'a, T> {
    fn next_back(&mut self) -> Option<Self::Item> {
        self.right.take().map(State::Node).or_else(|| {
            self.elem
                .take()
                .map(State::Elem)
                .or_else(|| self.left.take().map(State::Node))
        })
    }
}

impl<'a, T> Iterator for IterMut<'a, T> {
    type Item = &'a mut T;
    fn next(&mut self) -> Option<Self::Item> {
        loop {
            match self.0.front_mut().and_then(Iterator::next) {
                Some(State::Elem(elem)) => return Some(elem),
                Some(State::Node(node)) => self.0.push_front(node.iter_mut()),
                None => {
                    self.0.pop_front()?;
                }
            }
        }
    }
}

impl<'a, T> DoubleEndedIterator for IterMut<'a, T> {
    fn next_back(&mut self) -> Option<Self::Item> {
        loop {
            match self.0.back_mut().and_then(DoubleEndedIterator::next_back) {
                Some(State::Elem(elem)) => return Some(elem),
                Some(State::Node(node)) => self.0.push_back(node.iter_mut()),
                None => {
                    self.0.pop_back()?;
                }
            }
        }
    }
}
```

所有这些都是完全安全的，并且可以在稳定的 Rust 上运行！这最终落在了我们之前看到的简单结构案例中。Rust 知道你可以安全地将一个可变的引用分割成子字段。然后我们可以通过 Options（或者在分片的情况下，用空分片替换）来消耗掉这个引用并进行编码。
