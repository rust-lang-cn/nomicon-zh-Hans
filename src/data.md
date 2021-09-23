# Rust 中的数据布局

低层编程非常关心数据布局，这是个大问题。它也无孔不入地影响着语言的其他部分，所以我们将从挖掘数据在 Rust 中的布局方式开始。

本章最好与《The Reference》中的[类型布局][ref-type-layout]部分保持一致，并使之成为仅仅是多渲染了一份。本书刚写的时候，《The Reference》已经完全失修，而 Rust 秘典试图作为《The Reference》的部分替代。现在的情况不再是这样了，所以这一整章最好可以删除。

我们会把这一章再保留一段时间，但理想的情况是，你应该把任何新的事实或改进贡献给《The Reference》。

[ref-type-layout]: https://doc.rust-lang.org/reference/type-layout.html
