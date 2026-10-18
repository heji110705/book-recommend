# -*- coding: utf-8 -*-
"""
训练全部推荐算法并：
1. 离线评估，输出 RMSE/MAE、Precision@N/Recall@N/Coverage；
2. 生成评估图（matplotlib，供论文使用）；
3. 在全量数据上训练，离线生成热门与各算法的推荐结果入库。
"""
import json
from pathlib import Path

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from apps.recommender.models import RecommendResult
from apps.recommender.services import engine as engine_mod
from apps.recommender.services import evaluation
from config.settings import BASE_DIR


class Command(BaseCommand):
    help = "训练推荐算法、评估并离线生成推荐结果"

    def add_arguments(self, parser):
        parser.add_argument("--topn", type=int, default=15, help="每用户每算法推荐数量")
        parser.add_argument("--factors", type=int, default=12, help="SVD隐因子数")
        parser.add_argument("--no-plots", action="store_true", help="不生成图表")

    def handle(self, *args, **options):
        out_dir = Path(BASE_DIR) / "ml" / "output"
        out_dir.mkdir(parents=True, exist_ok=True)
        topn = options["topn"]
        factors = options["factors"]

        # 1) 离线评估
        self.stdout.write("① 离线评估中 ...")
        result = evaluation.evaluate(top_n=topn, n_factors=factors)
        with open(out_dir / "evaluation.json", "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2, default=str)
        self.print_metrics(result)

        if not options["no_plots"]:
            try:
                self.make_plots(result, out_dir)
            except Exception as e:  # 图表不影响主流程
                self.stdout.write(self.style.WARNING(f"图表生成失败：{e}"))

        # 2) 全量训练并生成推荐结果
        self.stdout.write("② 全量训练并生成推荐结果 ...")
        engine_mod.reset_engine()
        engine = engine_mod.get_engine(force_rebuild=True)
        RecommendResult.objects.all().delete()

        bulk = []
        # 热门（全局冷启动）
        for rank, (bid, score) in enumerate(engine.hot_items(n=topn), start=1):
            bulk.append(RecommendResult(user=None, book_id=bid, algo="hot",
                                        score=score, rank=rank))

        # 每个用户、每种算法
        for uid in engine.user_ids:
            u = engine.u_index[uid]
            for algo in ["usercf", "itemcf", "svd", "content", "hybrid"]:
                recs = engine.recommend(u, algo=algo, n=topn, exclude_seen=True)
                for rank, (bid, score) in enumerate(recs, start=1):
                    bulk.append(RecommendResult(user_id=uid, book_id=bid,
                                                algo=algo, score=score, rank=rank))
        RecommendResult.objects.bulk_create(bulk, batch_size=1000)

        self.stdout.write(self.style.SUCCESS(
            f"完成：共生成 {len(bulk)} 条推荐结果，指标与图表已保存到 {out_dir}"))

    def print_metrics(self, result):
        seeds = result.get("seeds", [42])
        self.stdout.write(f"\n（以下为 {len(seeds)} 个随机切分种子 {seeds} 上的均值）")
        self.stdout.write("\n=== 评分预测（RMSE / MAE，越小越好）===")
        for name, m in result["rating"].items():
            self.stdout.write(f"  {name:<16} RMSE={m['rmse']:.4f}  MAE={m['mae']:.4f}")
        self.stdout.write(f"\n=== Top-{result['top_n']} 推荐（准确率/召回/覆盖/多样性/新颖度）===")
        for name, m in result["topn"].items():
            self.stdout.write(
                f"  {name:<10} P={m['precision']:.4f}  R={m['recall']:.4f}  "
                f"Coverage={m['coverage']:.4f}  Diversity={m['diversity']:.4f}  "
                f"Novelty={m['novelty']:.3f}")

    def make_plots(self, result, out_dir):
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "Arial Unicode MS"]
        plt.rcParams["axes.unicode_minus"] = False

        rating = result["rating"]
        order = ["baseline_global", "baseline_item", "usercf", "itemcf", "content", "svd", "hybrid"]
        labels = {"baseline_global": "全局均值", "baseline_item": "物品均值",
                  "usercf": "UserCF", "itemcf": "ItemCF", "svd": "FunkSVD",
                  "content": "内容推荐", "hybrid": "混合推荐"}
        names = [labels[k] for k in order if k in rating]
        rmses = [rating[k]["rmse"] for k in order if k in rating]
        maes = [rating[k]["mae"] for k in order if k in rating]

        x = range(len(names))
        w = 0.38
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.bar([i - w / 2 for i in x], rmses, w, label="RMSE", color="#4e79a7")
        ax.bar([i + w / 2 for i in x], maes, w, label="MAE", color="#f28e2b")
        ax.set_xticks(list(x))
        ax.set_xticklabels(names, rotation=20)
        ax.set_ylabel("误差")
        ax.set_title("各算法评分预测误差对比")
        ax.legend()
        for i, v in enumerate(rmses):
            ax.text(i - w / 2, v + 0.01, f"{v:.3f}", ha="center", fontsize=8)
        for i, v in enumerate(maes):
            ax.text(i + w / 2, v + 0.01, f"{v:.3f}", ha="center", fontsize=8)
        fig.tight_layout()
        fig.savefig(out_dir / "rating_rmse_mae.png", dpi=150)
        plt.close(fig)

        # SVD 收敛曲线
        loss = result["svd_loss"]
        fig, ax = plt.subplots(figsize=(8, 4.5))
        ax.plot(range(1, len(loss) + 1), loss, marker="o", ms=3, color="#59a14f")
        ax.set_xlabel("迭代轮次 Epoch")
        ax.set_ylabel("训练 RMSE")
        ax.set_title("FunkSVD 矩阵分解训练收敛曲线")
        ax.grid(alpha=0.3)
        fig.tight_layout()
        fig.savefig(out_dir / "svd_convergence.png", dpi=150)
        plt.close(fig)

        # Top-N 指标
        topn = result["topn"]
        anames = [labels[k] for k in ["usercf", "itemcf", "svd", "content", "hybrid"]]
        prec = [topn[k]["precision"] for k in ["usercf", "itemcf", "svd", "content", "hybrid"]]
        rec = [topn[k]["recall"] for k in ["usercf", "itemcf", "svd", "content", "hybrid"]]
        x = range(len(anames))
        fig, ax = plt.subplots(figsize=(9, 5))
        ax.bar([i - w / 2 for i in x], prec, w, label="Precision@N", color="#4e79a7")
        ax.bar([i + w / 2 for i in x], rec, w, label="Recall@N", color="#e15759")
        ax.set_xticks(list(x))
        ax.set_xticklabels(anames)
        ax.set_ylabel("指标值")
        ax.set_title(f"各算法 Top-{result['top_n']} 推荐准确率与召回率")
        ax.legend()
        fig.tight_layout()
        fig.savefig(out_dir / "topn_precision_recall.png", dpi=150)
        plt.close(fig)
