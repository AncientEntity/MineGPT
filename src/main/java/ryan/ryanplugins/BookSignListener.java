package ryan.ryanplugins;

import org.bukkit.ChatColor;
import org.bukkit.Material;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.event.player.PlayerEditBookEvent;
import org.bukkit.inventory.meta.BookMeta;
import org.bukkit.plugin.java.JavaPlugin;

import java.util.Arrays;

public class BookSignListener implements Listener {

    private final JavaPlugin plugin;

    public BookSignListener(JavaPlugin plugin) {
        this.plugin = plugin;
    }

    @EventHandler
    public void onPlayerEditBook(PlayerEditBookEvent event) {
        Player player = event.getPlayer();
        BookMeta bookMeta = event.getNewBookMeta();

        if(bookMeta.getTitle().equals("gpt")) {
            //plugin.getLogger().info("Page: " + bookMeta.getPage(0));
            player.sendMessage(ChatColor.translateAlternateColorCodes('&',"GPT Processing"));
            String[] commands = GPTCommand.generateCommands(bookMeta.getPages().get(0));
            if(commands.length > 0) {
                player.sendMessage(ChatColor.translateAlternateColorCodes('&', "&6" + Arrays.toString(commands)));
            } else {
                player.sendMessage(ChatColor.translateAlternateColorCodes('&', "&6Rate Limit, Please Try Again."));
            }

            //for(int i = 0; i < commands.length; i++) {
            //    commands[i] = commands[i].substring(commands[i].indexOf(" ")+1); // To remove the "1. " etc
            //}

            GPTCommand.currentCommands = commands;

        }
    }
}