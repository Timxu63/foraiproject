using System.Linq;
using ForAI.Project.Editor.Addressables;
using NUnit.Framework;

namespace ForAI.Project.Tests.EditMode.Assets
{
    public sealed class AddressableContentPlannerTests
    {
        [Test]
        public void PlanEntries_AssignsSharedUiConfigAndFeatureGroups()
        {
            var assetPaths = new[]
            {
                "Assets/_Project/Content/Local/Shared/Fonts/MainFont.asset",
                "Assets/_Project/Content/Local/UI/Common/ButtonPrimary.prefab",
                "Assets/_Project/Content/Local/Config/GameBalance.asset",
                "Assets/_Project/Content/Local/Features/Inventory/UI/InventoryScreen.prefab",
                "Assets/_Project/Content/Local/Features/Shop/Config/ShopCatalog.asset"
            };

            AddressableContentPlanEntry[] entries = AddressableContentPlanner.PlanEntries(assetPaths).ToArray();

            AssertEntry(
                entries,
                "Assets/_Project/Content/Local/Shared/Fonts/MainFont.asset",
                "ForAI_Local_Shared",
                "shared/fonts/main_font");
            AssertEntry(
                entries,
                "Assets/_Project/Content/Local/UI/Common/ButtonPrimary.prefab",
                "ForAI_Local_UI",
                "ui/common/button_primary");
            AssertEntry(
                entries,
                "Assets/_Project/Content/Local/Config/GameBalance.asset",
                "ForAI_Local_Config",
                "config/game_balance");
            AssertEntry(
                entries,
                "Assets/_Project/Content/Local/Features/Inventory/UI/InventoryScreen.prefab",
                "ForAI_Local_Feature_Inventory",
                "features/inventory/ui/inventory_screen");
            AssertEntry(
                entries,
                "Assets/_Project/Content/Local/Features/Shop/Config/ShopCatalog.asset",
                "ForAI_Local_Feature_Shop",
                "features/shop/config/shop_catalog");
        }

        [Test]
        public void PlanEntries_IgnoresCodeMetadataEditorTestsAndOutsideRoot()
        {
            var assetPaths = new[]
            {
                "Assets/_Project/Content/Local/UI/Common/ButtonPrimary.prefab",
                "Assets/_Project/Content/Local/UI/Common/ButtonPrimary.prefab.meta",
                "Assets/_Project/Content/Local/UI/Common/ButtonPresenter.cs",
                "Assets/_Project/Content/Local/UI/Common/ForAI.Project.Content.asmdef",
                "Assets/_Project/Content/Local/UI/Editor/EditorOnly.asset",
                "Assets/_Project/Content/Local/Runtime/RuntimeOnly.asset",
                "Assets/_Project/Content/Local/UI/Tests/TestOnly.asset",
                "Assets/_Project/Runtime/UI/Core/UIPanelBase.cs",
                "Assets/_Project/HotUpdate/Features/Inventory/UI/InventoryScreen.cs"
            };

            AddressableContentPlanEntry[] entries = AddressableContentPlanner.PlanEntries(assetPaths).ToArray();

            Assert.That(entries, Has.Length.EqualTo(1));
            Assert.That(entries[0].AssetPath, Is.EqualTo("Assets/_Project/Content/Local/UI/Common/ButtonPrimary.prefab"));
            Assert.That(entries[0].GroupName, Is.EqualTo("ForAI_Local_UI"));
        }

        private static void AssertEntry(
            AddressableContentPlanEntry[] entries,
            string assetPath,
            string groupName,
            string address)
        {
            AddressableContentPlanEntry entry = entries.Single(candidate => candidate.AssetPath == assetPath);
            Assert.That(entry.GroupName, Is.EqualTo(groupName));
            Assert.That(entry.Address, Is.EqualTo(address));
        }
    }
}
