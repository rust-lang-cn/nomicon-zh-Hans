# Higher-Rank Trait Bounds (HRTBs)

Rust 的`Fn` trait 有一些黑魔法，例如，我们可以写出下面的代码：

```rust
struct Closure<F> {
    data: (u8, u16),
    func: F,
}

impl<F> Closure<F>
    where F: Fn(&(u8, u16)) -> &u8,
{
    fn call(&self) -> &u8 {
        (self.func)(&self.data)
    }
}

fn do_it(data: &(u8, u16)) -> &u8 { &data.0 }

fn main() {
    let clo = Closure { data: (0, 1), func: do_it };
    println!("{}", clo.call());
}
```

如果我们试图天真地用与生命周期部分相同的方式来对这段代码进行解语法糖，我们会遇到一些麻烦：

<!-- ignore: desugared code -->
```rust,ignore
struct Closure<F> {
    data: (u8, u16),
    func: F,
}

impl<F> Closure<F>
    // where F: Fn(&'??? (u8, u16)) -> &'??? u8,
{
    fn call<'a>(&'a self) -> &'a u8 {
        (self.func)(&self.data)
    }
}

fn do_it<'b>(data: &'b (u8, u16)) -> &'b u8 { &'b data.0 }

fn main() {
    'x: {
        let clo = Closure { data: (0, 1), func: do_it };
        println!("{}", clo.call());
    }
}
```

我们究竟应该如何表达`F`的 trait 约束上的生命周期？我们需要在那里提供一些生命周期，但是我们关心的生命周期在进入`call`的主体之前是不能被命名的! 而且，这并不是什么固定的生命周期；`call`可以与`&self`在这一时刻上的*任一*生命周期一起使用。

要完成这个事情，需要使用到高阶 Trait 约束（HRTB）的魔力。我们的解语法糖方式如下：

<!-- ignore: simplified code -->
```rust,ignore
where for<'a> F: Fn(&'a (u8, u16)) -> &'a u8,
```

（其中`Fn(a, b, c) -> d`本身只是不稳定的*真正的*`*Fn`特性的语法糖）

`for<'a>`可以理解为“对于所有`'a`的可能”，并且基本上产生一个*无限的* F 必须满足的 trait 约束的列表。不过不用紧张，在`Fn` trait 之外，我们遇到 HRTB 的地方不多，即使是那些地方，我们也有一个很好的魔法糖来处理普通的情况。
