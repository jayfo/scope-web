import { createMuiTheme } from '@material-ui/core/styles';

declare module '@material-ui/core/styles/createMuiTheme' {
    interface Theme {
        customPalette: {
            subtle: React.CSSProperties['color'];
            discrete10: string[];
        };
        customSizes: {
            drawerWidth: number;
            contentsMenuWidth: number;
            headerHeight: number;
            footerHeight: number;
        };
    }
    interface ThemeOptions {
        customPalette: {
            subtle: React.CSSProperties['color'];
            discrete10: string[];
        };
        customSizes: {
            drawerWidth: number;
            contentsMenuWidth: number;
            headerHeight: number;
            footerHeight: number;
        };
    }
}

export default function createAppTheme() {
    return createMuiTheme({
        customPalette: {
            subtle: '#eeeeee',
            discrete10: [
                '#1f77b4',
                '#ff7f0e',
                '#2ca02c',
                '#d62728',
                '#9467bd',
                '#8c564b',
                '#e377c2',
                '#7f7f7f',
                '#bcbd22',
                '#17becf',
            ],
        },
        customSizes: {
            drawerWidth: 240,
            contentsMenuWidth: 240,
            headerHeight: 64,
            footerHeight: 80,
        },
    });
}